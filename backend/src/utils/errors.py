"""
Custom exception classes for SmartRetail-Sync.
Provides structured error handling across the application.
"""

from typing import Optional, Any


class SmartRetailException(Exception):
    """Base exception for SmartRetail-Sync."""
    
    def __init__(
        self,
        message: str,
        error_code: str = "INTERNAL_ERROR",
        status_code: int = 500,
        details: Optional[Any] = None
    ):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details
        super().__init__(self.message)


class DatabaseError(SmartRetailException):
    """Database operation error."""
    
    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(
            message=message,
            error_code="DATABASE_ERROR",
            status_code=500,
            details=details
        )


class ValidationError(SmartRetailException):
    """Data validation error."""
    
    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            status_code=400,
            details=details
        )


class NotFoundError(SmartRetailException):
    """Resource not found error."""
    
    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(
            message=message,
            error_code="NOT_FOUND",
            status_code=404,
            details=details
        )


class KeyVaultError(SmartRetailException):
    """Azure Key Vault operation error."""
    
    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(
            message=message,
            error_code="KEYVAULT_ERROR",
            status_code=500,
            details=details
        )


class AuthenticationError(SmartRetailException):
    """Authentication error."""
    
    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(
            message=message,
            error_code="AUTH_ERROR",
            status_code=401,
            details=details
        )


class DuplicateError(SmartRetailException):
    """Duplicate resource error."""
    
    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(
            message=message,
            error_code="DUPLICATE_ERROR",
            status_code=409,
            details=details
        )
