"""Project exception hierarchy."""


class IlluminateMCPError(Exception):
    """Base project exception."""


class ConfigError(IlluminateMCPError):
    """Raised when startup configuration is invalid."""


class PolicyError(IlluminateMCPError):
    """Raised when SQL fails policy validation."""


class ToolError(IlluminateMCPError):
    """Raised when a tool call cannot be completed."""
