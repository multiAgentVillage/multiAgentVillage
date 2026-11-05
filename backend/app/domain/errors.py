"""Stable business failures shared by the invoker and infrastructure codecs."""


class CommandDecodeError(ValueError):
    """A persisted command has an unsupported type/version or invalid payload."""


class CommandRejected(ValueError):
    """A valid command cannot take effect in the current world."""
