"""GoF Command invoker; all world effects share one explicit UnitOfWork."""
from collections.abc import Callable
from enum import StrEnum

from app.domain.contract_types import ContractModel, Identifier
from app.domain.commands import CommandReceipt, CommandStatus
from app.domain.errors import CommandDecodeError, CommandRejected
from app.domain.run_states import Disposition
from app.ports.repositories import CommandCodec, UnitOfWork


class ProcessStatus(StrEnum):
    IDLE = "idle"
    DEFERRED = "deferred"
    APPLIED = "applied"
    REJECTED = "rejected"


class ProcessResult(ContractModel):
    status: ProcessStatus
    command_id: Identifier | None = None
    event_ids: tuple[Identifier, ...] = ()


class CommandProcessor:
    def __init__(self, uow_factory: Callable[[], UnitOfWork], codec: CommandCodec) -> None:
        self.uow_factory = uow_factory
        self.codec = codec

    async def process_next(self, run_id: str) -> ProcessResult:
        async with self.uow_factory() as uow:
            # The owning run lock serializes command selection and seq allocation.
            world = await uow.worlds.load(run_id, for_update=True)
            envelope = await uow.commands.next_eligible(run_id, control_first=True)
            if envelope is None:
                return ProcessResult(status=ProcessStatus.IDLE)
            try:
                command = self.codec.decode(envelope)
                disposition = world.state.classify(command.kind)
                if disposition == Disposition.DEFER:
                    await uow.commands.defer(envelope.command_id)
                    return ProcessResult(status=ProcessStatus.DEFERRED, command_id=envelope.command_id)
                validation = world.validate(command)
                if disposition == Disposition.REJECT or not validation.allowed:
                    raise CommandRejected(validation.reason or "当前状态不允许执行命令")
                drafts = command.execute(world)
            except (CommandDecodeError, CommandRejected) as error:
                await uow.commands.finish(CommandReceipt(
                    command_id=envelope.command_id, status=CommandStatus.REJECTED, reason=str(error),
                ))
                await uow.commit()
                return ProcessResult(status=ProcessStatus.REJECTED, command_id=envelope.command_id)
            await uow.worlds.save(world)
            events = await uow.events.append_with_seq(run_id, drafts)
            await uow.outbox.add(events)
            event_ids = tuple(event.event_id for event in events)
            await uow.commands.finish(CommandReceipt(
                command_id=envelope.command_id, status=CommandStatus.APPLIED, result_event_ids=event_ids,
            ))
            await uow.commit()
            return ProcessResult(status=ProcessStatus.APPLIED, command_id=envelope.command_id, event_ids=event_ids)
