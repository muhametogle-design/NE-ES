"""Authentication model import path.

User remains defined in tenancy for compatibility with existing integrations;
its optional one-to-one ``teacher`` relationship is the staff profile binding.
"""
from app.models.tenancy import User

__all__ = ["User"]
