"""Safety-zone geometry: line configuration, helmet association, crossing logic.

This sub-package is intentionally free of heavy CV imports so that the detection
logic can be unit-tested without OpenCV / torch installed.
"""

from ai_repo.zones.line_crossing import (
    CrossedLine,
    HelmetAssociator,
    HelmetStatus,
    LineConfig,
    LineCrossingDetector,
    SafetyLine,
)

__all__ = [
    "CrossedLine",
    "HelmetAssociator",
    "HelmetStatus",
    "LineConfig",
    "LineCrossingDetector",
    "SafetyLine",
]
