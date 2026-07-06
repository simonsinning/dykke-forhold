from __future__ import annotations

import json
from datetime import datetime, timedelta
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from .models import ForecastBundle, HourlyPoint
from .utils import parse_time


class OpenMeteoProvider:
    """Fetches weather and marine forecasts without requiring an API key."""

    WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
    MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"
    CACHE_SECONDS = 600

    def __init__(self):
        self._cache: dict[tuple[float, float], tuple[datetime, ForecastBundle]] = {}

    def fetch(self, latitude: float, longitude: float) -> ForecastBundle:
        cache_key = (round(latitude, 4), round(longitude, 4))
        cached = self._cache.get(cache_key)
        if cached and datetime.now() - cached[0] < timedelta(seconds=self.CACHE_SECONDS):
            return cached[1]

        warnings: list[str] = []
        try:
            weather = self._fetch_json(
                self.WEATHER_URL,
                {
                    "latitude": latitude,
                    "longitude": longitude,
                    "hourly": "wind_speed_10m,wind_direction_10m,wind_gusts_10m,precipitation",
                    "past_days": 3,
                    "forecast_days": 3,
                    "timezone": "Europe/Copenhagen",
                    "wind_speed_unit": "ms",
                },
            )
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            warnings.append(f"Kunne ikke hente vejrdata: {exc}")
            weather = {}

        try:
            marine = self._fetch_json(
                self.MARINE_URL,
                {
                    "latitude": latitude,
                    "longitude": longitude,
                    "hourly": (
                        "wave_height,wave_direction,wave_period,"
                        "ocean_current_velocity,ocean_current_direction,sea_surface_temperature"
                    ),
                    "past_days": 3,
                    "forecast_days": 3,
                    "timezone": "Europe/Copenhagen",
                    "cell_selection": "sea",
                },
            )
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            warnings.append(f"Kunne ikke hente havdata: {exc}")
            marine = {}

        points = self._merge(weather.get("hourly", {}), marine.get("hourly", {}))
        if not points:
            warnings.append("Bruger demodata, fordi live-data ikke kunne hentes.")
            points = self._demo_points()

        source = "Open-Meteo live-data" if len(warnings) == 0 else "Demo/fallback med delvise live-data"
        forecast = ForecastBundle(points=points, source=source, warnings=warnings)
        self._cache[cache_key] = (datetime.now(), forecast)
        return forecast

    def _fetch_json(self, base_url: str, params: dict[str, object]) -> dict:
        url = f"{base_url}?{urlencode(params)}"
        with urlopen(url, timeout=12) as response:
            if response.status >= 400:
                raise HTTPError(url, response.status, response.reason, response.headers, None)
            return json.loads(response.read().decode("utf-8"))

    def _merge(self, weather: dict, marine: dict) -> list[HourlyPoint]:
        times = sorted(set(weather.get("time", [])) | set(marine.get("time", [])))
        points = []
        weather_index = {time: idx for idx, time in enumerate(weather.get("time", []))}
        marine_index = {time: idx for idx, time in enumerate(marine.get("time", []))}

        for time in times:
            wi = weather_index.get(time)
            mi = marine_index.get(time)
            points.append(
                HourlyPoint(
                    time=parse_time(time),
                    wind_speed=self._value(weather, "wind_speed_10m", wi),
                    wind_direction=self._value(weather, "wind_direction_10m", wi),
                    wind_gusts=self._value(weather, "wind_gusts_10m", wi),
                    precipitation=self._value(weather, "precipitation", wi),
                    wave_height=self._value(marine, "wave_height", mi),
                    wave_direction=self._value(marine, "wave_direction", mi),
                    wave_period=self._value(marine, "wave_period", mi),
                    current_velocity=self._kmh_to_ms(self._value(marine, "ocean_current_velocity", mi)),
                    current_direction=self._value(marine, "ocean_current_direction", mi),
                    sea_temperature=self._value(marine, "sea_surface_temperature", mi),
                )
            )
        return points

    def _value(self, data: dict, key: str, index: int | None) -> float | None:
        if index is None:
            return None
        values = data.get(key, [])
        if index >= len(values):
            return None
        return values[index]

    def _kmh_to_ms(self, value: float | None) -> float | None:
        if value is None:
            return None
        return value / 3.6

    def _demo_points(self) -> list[HourlyPoint]:
        start = datetime.now().replace(minute=0, second=0, microsecond=0) - timedelta(hours=72)
        points = []
        for hour in range(144):
            time = start + timedelta(hours=hour)
            diurnal = 0.7 if 9 <= time.hour <= 18 else 0.35
            points.append(
                HourlyPoint(
                    time=time,
                    wind_speed=3.0 + (hour % 18) * 0.18,
                    wind_direction=(240 + hour * 2) % 360,
                    wind_gusts=5.5 + (hour % 9) * 0.22,
                    precipitation=0.0 if hour % 17 else 0.8,
                    wave_height=0.25 + diurnal * 0.15 + (hour % 11) * 0.015,
                    wave_direction=(230 + hour) % 360,
                    wave_period=3.2 + (hour % 5) * 0.2,
                    current_velocity=0.12 + (hour % 8) * 0.015,
                    current_direction=(90 + hour * 3) % 360,
                    sea_temperature=15.0,
                )
            )
        return points
