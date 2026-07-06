from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class HourlyPoint:
    time: datetime
    wind_speed: float | None = None
    wind_direction: float | None = None
    wind_gusts: float | None = None
    precipitation: float | None = None
    wave_height: float | None = None
    wave_direction: float | None = None
    wave_period: float | None = None
    current_velocity: float | None = None
    current_direction: float | None = None
    sea_temperature: float | None = None


@dataclass(frozen=True)
class ForecastBundle:
    points: list[HourlyPoint]
    source: str
    warnings: list[str]

    def summary(self) -> dict[str, Any]:
        latest = self.points[-1] if self.points else None
        return {
            "source": self.source,
            "warnings": self.warnings,
            "points": len(self.points),
            "from": self.points[0].time.isoformat(timespec="minutes") if self.points else None,
            "to": latest.time.isoformat(timespec="minutes") if latest else None,
        }

    def series(self) -> list[dict[str, Any]]:
        return [
            {
                "time": point.time.isoformat(timespec="minutes"),
                "wind_speed": point.wind_speed,
                "wind_direction": point.wind_direction,
                "wind_gusts": point.wind_gusts,
                "precipitation": point.precipitation,
                "wave_height": point.wave_height,
                "wave_direction": point.wave_direction,
                "wave_period": point.wave_period,
                "current_velocity": point.current_velocity,
                "current_direction": point.current_direction,
                "sea_temperature": point.sea_temperature,
            }
            for point in self.points
        ]
