"""Domain errors. The API layer maps these to HTTP status codes in one place."""


class DomainError(Exception):
    """Base class for errors the user can act on."""


class NotFoundError(DomainError):
    """A customer or account does not exist (or is not visible to this caller)."""


class InvalidRequestError(DomainError):
    """The request is well-formed but makes no sense for this data."""
