"""Errors meant for the user. The message is an English UI message ID, translated by the UI."""


class UserError(Exception):
    """A condition the user can understand and resolve; shown instead of a generic failure."""


class ProviderUnavailableError(UserError):
    """A connection, account or server problem rather than a bad image. Pauses the batch."""
