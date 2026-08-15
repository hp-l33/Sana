"""Sol Engine: a small contract for producing and running optimized model plugins."""

from .contracts import ExecutionPlan, ModelInfo
from .engine import Engine

__all__ = ["Engine", "ExecutionPlan", "ModelInfo"]
__version__ = "0.2.0.dev0"
