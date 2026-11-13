"""Domain-level validation error shared by all pure domain modules."""


class DomainValidationError(Exception):
    """Structured validation failure (never NaN/inf or silent defaults)."""

    def __init__(self, code: str, field: str, message: str) -> None:
        super().__init__(f"{code} [{field}]: {message}")
        self.code = code
        self.field = field
        self.message = message
