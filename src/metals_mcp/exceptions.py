
class MetalsMCPError(Exception):
    """Base application error."""


class ConfigurationError(MetalsMCPError):
    """Configuration error."""


class ValidationError(MetalsMCPError):
    """Validation error."""


class NotFoundError(MetalsMCPError):
    """Requested object was not found."""


class AuthorizationError(MetalsMCPError):
    """Authorization failed."""
