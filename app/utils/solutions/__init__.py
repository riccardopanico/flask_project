# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

# Import only from existing modules
from .solutions import BaseSolution, SolutionAnnotator, SolutionResults
from .config import SolutionConfig

__all__ = (
    "BaseSolution",
    "SolutionAnnotator", 
    "SolutionResults",
    "SolutionConfig",
)
