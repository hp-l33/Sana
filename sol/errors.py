class SolError(Exception):
    """Base class for expected, user-facing Sol failures."""


class DiscoveryError(SolError):
    """A model plugin manifest is invalid or ambiguous."""


class AdaptationError(SolError):
    """An adaptation lifecycle operation is invalid."""
