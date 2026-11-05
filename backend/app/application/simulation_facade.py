"""GoF Facade: submit durable commands without executing the world in HTTP."""
from app.domain.commands import CommandEnvelope, CommandReceipt
from app.application.replay_service import ReplayService
from app.ports.repositories import CommandInbox, ReadService


class SimulationFacade:
    def __init__(self, inbox: CommandInbox, reads: ReadService, replay: ReplayService | None = None) -> None:
        self.inbox = inbox
        self.reads = reads
        self.replay = replay

    async def submit(self, envelope: CommandEnvelope) -> CommandReceipt:
        return await self.inbox.append(envelope)
