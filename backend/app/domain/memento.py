"""Opaque snapshot contract; no restoration or serialization logic yet."""
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class WorldMemento:
    run_id: str
    seq: int
    sim_time_ms: int
    schema_version: int
    state_hash: str
    _opaque_state_json: str


class ReadOnlyView(Protocol):
    """U07 public replay result; it grants no world or command write capabilities."""

    @property
    def run_id(self) -> str: ...
    @property
    def seq(self) -> int: ...
    @property
    def sim_time_ms(self) -> int: ...
    @property
    def snapshot(self) -> WorldMemento: ...
