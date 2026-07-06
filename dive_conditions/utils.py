from __future__ import annotations

import math
from datetime import datetime


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)


def angle_distance(a: float | None, b: float | None) -> float:
    if a is None or b is None:
        return 180.0
    return abs((a - b + 180.0) % 360.0 - 180.0)


def direction_match(direction: float | None, centers: list[float], tolerance: float) -> float:
    if direction is None or not centers:
        return 0.0
    distance = min(angle_distance(direction, center) for center in centers)
    if distance >= tolerance:
        return 0.0
    return 1.0 - (distance / tolerance)


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def safe_avg(values: list[float | None]) -> float | None:
    clean = [value for value in values if value is not None and not math.isnan(value)]
    if not clean:
        return None
    return sum(clean) / len(clean)


def safe_max(values: list[float | None]) -> float | None:
    clean = [value for value in values if value is not None and not math.isnan(value)]
    if not clean:
        return None
    return max(clean)
