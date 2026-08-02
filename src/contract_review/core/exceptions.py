class ContractReviewError(Exception):
    """Base exception for contract review domain errors."""


class UnsupportedDocumentTypeError(ContractReviewError):
    """Raised when an uploaded contract file type is not supported."""


class UploadTooLargeError(ContractReviewError):
    """Raised when an uploaded file exceeds the configured size limit."""


class UnsafeUploadError(ContractReviewError):
    """Raised when an upload extension and file signature are unsafe or inconsistent."""


class DocumentTextExtractionError(ContractReviewError):
    """Raised when a supported document has no usable text for review."""


class LLMConfigurationError(ContractReviewError):
    """Raised when external LLM API configuration is incomplete."""
