"""Exceptions for background import jobs."""


class ImportJobCancelled(Exception):
    """Raised when a cooperative cancel is requested mid-import."""


class ImportJobConflictError(Exception):
    """Another import job is already queued or running."""


class ImportJobNotFoundError(Exception):
    """No job exists for the given id."""
