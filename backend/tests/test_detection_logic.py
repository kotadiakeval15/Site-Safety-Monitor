"""Unit tests for the preserved AI detection logic (ai_repo)."""

from __future__ import annotations

import time

from ai_repo.detection.detector import HelmetDetection, PersonHelmetDetector
from ai_repo.tracking.cooldown import CooldownTracker
from ai_repo.zones.line_crossing import (
    CrossedLine,
    HelmetAssociator,
    LineConfig,
    LineCrossingDetector,
    SafetyLine,
)


def _horizontal(color: str, y: float) -> SafetyLine:
    """A full-width horizontal line at fractional height ``y``."""

    return SafetyLine(color=color, x1=0.0, y1=y, x2=1.0, y2=y)


def test_compute_foot_is_bottom_center():
    fx, fy = HelmetAssociator.compute_foot((10, 20, 30, 80))
    assert fx == 20.0
    assert fy == 80.0


def test_helmet_inside_head_region_detected():
    associator = HelmetAssociator()
    helmets = [
        HelmetDetection(
            cx=50.0,
            cy=20.0,
            conf=0.9,
            x1=45.0,
            y1=15.0,
            x2=55.0,
            y2=25.0,
            label="helmet",
            is_compliant=True,
        )
    ]
    safe, conf = associator.evaluate_helmet_status((0, 0, 100, 100), helmets)
    assert safe is True
    assert conf == 0.9


def test_helmet_below_head_region_not_detected():
    associator = HelmetAssociator()
    helmets = [
        HelmetDetection(
            cx=50.0,
            cy=80.0,
            conf=0.9,
            x1=45.0,
            y1=75.0,
            x2=55.0,
            y2=85.0,
            label="helmet",
            is_compliant=True,
        )
    ]
    safe, _ = associator.evaluate_helmet_status((0, 0, 100, 100), helmets)
    assert safe is False


def test_non_industrial_helmet_in_head_region_is_violation():
    associator = HelmetAssociator()
    helmets = [
        HelmetDetection(
            cx=50.0,
            cy=20.0,
            conf=0.9,
            x1=45.0,
            y1=15.0,
            x2=55.0,
            y2=25.0,
            label="helmet",
            is_compliant=False,
        )
    ]
    safe, _ = associator.evaluate_helmet_status((0, 0, 100, 100), helmets)
    assert safe is False


def test_helmet_status_updates_when_compliance_changes():
    associator = HelmetAssociator()
    bbox = (0, 0, 100, 100)
    non_compliant = [
        HelmetDetection(50.0, 20.0, 0.9, 45.0, 15.0, 55.0, 25.0, "helmet", False)
    ]
    compliant = [
        HelmetDetection(50.0, 20.0, 0.9, 45.0, 15.0, 55.0, 25.0, "helmet", True)
    ]
    assert associator.evaluate_helmet_status(bbox, non_compliant)[0] is False
    assert associator.evaluate_helmet_status(bbox, compliant)[0] is True
    assert associator.evaluate_helmet_status(bbox, [])[0] is False


def test_helmet_label_kind_mapping():
    assert PersonHelmetDetector._helmet_label_kind("helmet") == "compliant"
    assert PersonHelmetDetector._helmet_label_kind("safety helmet") == "compliant"
    assert PersonHelmetDetector._helmet_label_kind("industrial_helmet") == "compliant"
    assert PersonHelmetDetector._helmet_label_kind("head") == "violation"
    assert PersonHelmetDetector._helmet_label_kind("no helmet") == "violation"
    assert PersonHelmetDetector._helmet_label_kind("without_helmet") == "violation"
    assert PersonHelmetDetector._helmet_label_kind("person") is None


def test_helmet_status_prefers_compliant_over_head_detection():
    associator = HelmetAssociator()
    bbox = (0, 0, 100, 100)
    mixed = [
        HelmetDetection(50.0, 20.0, 0.7, 45.0, 15.0, 55.0, 25.0, "head", False),
        HelmetDetection(50.0, 20.0, 0.9, 45.0, 15.0, 55.0, 25.0, "helmet", True),
    ]
    safe, conf = associator.evaluate_helmet_status(bbox, mixed)
    assert safe is True
    assert conf == 0.9


def test_helmet_alert_cooldown_is_ten_minutes():
    cooldown = CooldownTracker(600.0)
    assert cooldown.should_fire(1, "helmet_violation") is True
    assert cooldown.should_fire(1, "helmet_violation") is False


def test_helmet_inside_upper_body_detected():
    associator = HelmetAssociator()
    has, conf = associator.has_helmet((0, 0, 100, 100), [(50, 20, 0.9)])
    assert has is True
    assert conf == 0.9


def test_helmet_below_upper_body_not_detected():
    associator = HelmetAssociator()
    has, _ = associator.has_helmet((0, 0, 100, 100), [(50, 80, 0.9)])
    assert has is False


def test_classify_zone_bands_far_to_near():
    # Green (far) → yellow → red (near camera at bottom of frame).
    config = LineConfig(
        [_horizontal("green", 0.35), _horizontal("yellow", 0.45), _horizontal("red", 0.55)]
    )
    detector = LineCrossingDetector(config, frame_width=100, frame_height=100)

    assert detector.classify_zone(50.0, 20.0) == "safe"  # before green (far)
    assert detector.classify_zone(50.0, 40.0) == "safe"  # between green and yellow
    assert detector.classify_zone(50.0, 50.0) == "yellow"  # between yellow and red
    assert detector.classify_zone(50.0, 60.0) == "red"  # after red toward camera


def test_line_crossing_downward():
    config = LineConfig(
        [_horizontal("green", 0.55), _horizontal("yellow", 0.45), _horizontal("red", 0.35)]
    )
    detector = LineCrossingDetector(config, frame_width=100, frame_height=100)
    # First observation seeds history, no crossing.
    assert detector.evaluate(1, 50.0, 10.0) == []
    # Moving from y=10 to y=40 crosses the red line (0.35 * 100 = 35).
    crossed = detector.evaluate(1, 50.0, 40.0)
    assert CrossedLine.RED in crossed


def test_line_crossing_bidirectional():
    config = LineConfig([_horizontal("green", 0.55)])
    detector = LineCrossingDetector(config, frame_width=100, frame_height=100)
    detector.evaluate(1, 50.0, 60.0)
    # Moving upward across green (55) should also fire.
    crossed = detector.evaluate(1, 50.0, 50.0)
    assert CrossedLine.GREEN in crossed


def test_line_crossing_ignored_outside_segment():
    # A short segment on the left half; a foot crossing on the right must not fire.
    config = LineConfig([SafetyLine("red", 0.0, 0.5, 0.4, 0.5)])
    detector = LineCrossingDetector(config, frame_width=100, frame_height=100)
    detector.evaluate(1, 80.0, 40.0)
    crossed = detector.evaluate(1, 80.0, 60.0)
    assert crossed == []


def test_diagonal_line_crossing():
    # Diagonal from top-left to bottom-right; foot moving across it fires.
    config = LineConfig([SafetyLine("red", 0.0, 0.0, 1.0, 1.0)])
    detector = LineCrossingDetector(config, frame_width=100, frame_height=100)
    detector.evaluate(1, 60.0, 40.0)  # above the diagonal
    crossed = detector.evaluate(1, 40.0, 60.0)  # below the diagonal
    assert CrossedLine.RED in crossed


def test_line_detector_prune():
    detector = LineCrossingDetector(
        LineConfig([_horizontal("red", 0.5)]), frame_width=100, frame_height=100
    )
    detector.evaluate(1, 50.0, 10.0)
    detector.evaluate(2, 50.0, 10.0)
    detector.prune({1})
    assert all(key[0] != 2 for key in detector._previous_side)


def test_cooldown_suppresses_duplicates():
    cooldown = CooldownTracker(cooldown_seconds=10.0)
    assert cooldown.should_fire(1, "helmet_violation") is True
    assert cooldown.should_fire(1, "helmet_violation") is False


def test_cooldown_allows_after_window():
    cooldown = CooldownTracker(cooldown_seconds=0.01)
    assert cooldown.should_fire(1, "line_crossing", "red") is True
    time.sleep(0.02)
    assert cooldown.should_fire(1, "line_crossing", "red") is True


def test_cooldown_reset_allows_immediate_refire():
    cooldown = CooldownTracker(cooldown_seconds=10.0)
    assert cooldown.should_fire(1, "red_zone", "occupied") is True
    assert cooldown.should_fire(1, "red_zone", "occupied") is False
    cooldown.reset(1, "red_zone", "occupied")
    assert cooldown.should_fire(1, "red_zone", "occupied") is True


def test_cooldown_keys_are_independent():
    cooldown = CooldownTracker(cooldown_seconds=10.0)
    assert cooldown.should_fire(1, "line_crossing", "green") is True
    assert cooldown.should_fire(1, "line_crossing", "red") is True
    assert cooldown.should_fire(2, "line_crossing", "green") is True
