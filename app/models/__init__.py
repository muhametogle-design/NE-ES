"""ORM models. Importing this package registers every model on ``Base``."""
from app.models.finance import Invoice, Payment  # noqa: F401
from app.models.student import Student  # noqa: F401
from app.models.user import User  # noqa: F401

__all__ = ["User", "Student", "Invoice", "Payment"]
