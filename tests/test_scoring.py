from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from dive_conditions.models import ForecastBundle, HourlyPoint
from dive_conditions.scoring import ScoreEngine


class ScoreEngineTest(unittest.TestCase):
    def setUp(self):
        self.spot = {
            "id": "test",
            "name": "Testspot",
            "bad_wind_directions": [90],
            "good_wind_directions": [270],
            "direction_tolerance": 45,
            "typical_visibility_m": 4.0,
            "bottom_stability_bonus": 0,
            "sensitivity": {"wind": 1, "waves": 1, "rain": 1, "current": 1},
        }
        self.engine = ScoreEngine()

    def test_offshore_calm_scores_higher_than_onshore_rough(self):
        calm = ForecastBundle(
            points=self._points(wind_direction=270, wind_speed=3, wave_height=0.2, rain=0),
            source="test",
            warnings=[],
        )
        rough = ForecastBundle(
            points=self._points(wind_direction=90, wind_speed=9, wave_height=1.1, rain=1.2),
            source="test",
            warnings=[],
        )

        calm_score = self.engine.score_spot(self.spot, calm)["best"]["score"]
        rough_score = self.engine.score_spot(self.spot, rough)["best"]["score"]

        self.assertGreater(calm_score, rough_score)
        self.assertGreater(calm_score, 60)
        self.assertLess(rough_score, 45)

    def test_local_fjord_profile_requires_more_calm_than_robust_reef(self):
        robust_reef = {
            **self.spot,
            "visibility_model": {
                "base_score": 84,
                "sediment_risk": 0.4,
                "shallow_factor": 0.8,
                "runoff_sensitivity": 0.5,
                "algae_sensitivity": 0.8,
                "current_sensitivity": 0.8,
                "water_exchange": 1.2,
                "required_calm_hours": 18,
                "calm_wind_ms": 5.2,
                "calm_wave_m": 0.45,
            },
        }
        fjord_mud = {
            **self.spot,
            "visibility_model": {
                "base_score": 52,
                "sediment_risk": 2.4,
                "shallow_factor": 1.6,
                "runoff_sensitivity": 1.6,
                "algae_sensitivity": 1.3,
                "current_sensitivity": 0.9,
                "water_exchange": 0.45,
                "required_calm_hours": 96,
                "calm_wind_ms": 3.2,
                "calm_wave_m": 0.18,
            },
        }
        forecast = ForecastBundle(
            points=self._points(wind_direction=270, wind_speed=3, wave_height=0.2, rain=0),
            source="test",
            warnings=[],
        )

        reef_score = self.engine.score_spot(robust_reef, forecast)["best"]["score"]
        fjord_score = self.engine.score_spot(fjord_mud, forecast)["best"]["score"]

        self.assertGreater(reef_score, fjord_score + 20)

    def _points(self, wind_direction, wind_speed, wave_height, rain):
        start = datetime.now().replace(minute=0, second=0, microsecond=0) - timedelta(hours=72)
        return [
            HourlyPoint(
                time=start + timedelta(hours=hour),
                wind_speed=wind_speed,
                wind_direction=wind_direction,
                wind_gusts=wind_speed + 2,
                precipitation=rain,
                wave_height=wave_height,
                wave_direction=wind_direction,
                wave_period=3,
                current_velocity=0.2,
                current_direction=180,
                sea_temperature=15,
            )
            for hour in range(144)
        ]


if __name__ == "__main__":
    unittest.main()
