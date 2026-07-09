class ContractReviewError(Exception):
    """Base exception for contract review domain errors."""


class UnsupportedDocumentTypeError(ContractReviewError):
    """Raised when an uploaded contract file type is not supported."""


class UploadTooLargeError(ContractReviewError):
    """Raised when an uploaded file exceeds the configured size limit."""


class LLMConfigurationError(ContractReviewError):
    """Raised when external LLM API configuration is incomplete."""
