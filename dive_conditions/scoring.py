from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from .models import ForecastBundle, HourlyPoint
from .utils import clamp, direction_match, safe_avg, safe_max


class ScoreEngine:
    def score_spot(self, spot: dict[str, Any], forecast: ForecastBundle) -> dict[str, Any]:
        now = datetime.now().replace(minute=0, second=0, microsecond=0)
        windows = [
            ("Nu", now, now + timedelta(hours=6)),
            ("I aften", now.replace(hour=18), now.replace(hour=23)),
            ("I morgen", (now + timedelta(days=1)).replace(hour=9), (now + timedelta(days=1)).replace(hour=18)),
            ("Om 2 dage", (now + timedelta(days=2)).replace(hour=9), (now + timedelta(days=2)).replace(hour=18)),
        ]

        ratings = [self._score_window(spot, forecast.points, label, start, end) for label, start, end in windows]
        best = max(ratings, key=lambda item: item["score"]) if ratings else None
        return {
            "generated_at": datetime.now().isoformat(timespec="minutes"),
            "ratings": ratings,
            "best": best,
            "model": "Lokal kyst-sigtbarhedsmodel v2",
        }

    def _score_window(
        self,
        spot: dict[str, Any],
        points: list[HourlyPoint],
        label: str,
        start: datetime,
        end: datetime,
    ) -> dict[str, Any]:
        history_start = start - timedelta(hours=72)
        history = [point for point in points if history_start <= point.time <= start]
        target = [point for point in points if start <= point.time <= end]
        if not target:
            target = [point for point in points if point.time >= start][:6]

        profile = self._profile(spot)
        sensitivity = spot.get("sensitivity", {})
        wind_factor = self._float(sensitivity.get("wind"), 1.0)
        wave_factor = self._float(sensitivity.get("waves"), 1.0)
        rain_factor = self._float(sensitivity.get("rain"), 1.0)
        current_factor = self._float(sensitivity.get("current"), 1.0)

        onshore = [float(value) for value in spot.get("bad_wind_directions", [])]
        offshore = [float(value) for value in spot.get("good_wind_directions", [])]
        tolerance = self._float(spot.get("direction_tolerance"), 55.0)

        sediment_risk = self._float(profile.get("sediment_risk"), 1.0)
        shallow_factor = self._float(profile.get("shallow_factor"), 1.0)
        runoff_sensitivity = self._float(profile.get("runoff_sensitivity"), 1.0)
        algae_sensitivity = self._float(profile.get("algae_sensitivity"), 1.0)
        current_sensitivity = self._float(profile.get("current_sensitivity"), 1.0)
        water_exchange = self._float(profile.get("water_exchange"), 1.0)
        required_calm_hours = self._float(profile.get("required_calm_hours"), 36.0)
        calm_wind_ms = self._float(profile.get("calm_wind_ms"), 4.8)
        calm_wave_m = self._float(profile.get("calm_wave_m"), 0.35)

        wind_memory = 0.0
        wave_memory = 0.0
        onshore_wind_hours = 0.0
        offshore_relief = 0.0
        local_sector_pressure = 0.0

        for point in history:
            age_hours = max(0.0, (start - point.time).total_seconds() / 3600)
            weight = self._history_weight(age_hours)
            wind = point.wind_speed or 0.0
            wave = point.wave_height or 0.0
            period = point.wave_period or 4.0

            onshore_match = direction_match(point.wind_direction, onshore, tolerance)
            offshore_match = direction_match(point.wind_direction, offshore, tolerance)
            fetch_factor = self._direction_factor(point.wind_direction, profile.get("fetch_sectors", []), 0.85)
            exposure = fetch_factor * (1.0 + onshore_match * 0.45) * (1.0 - offshore_match * 0.25)

            onshore_wind_hours += onshore_match * weight
            offshore_relief += offshore_match * min(wind, 8.0) * weight
            wind_memory += (wind / 6.0) ** 2 * exposure * weight
            wave_memory += wave * (1.0 + max(0.0, period - 4.0) * 0.08) * exposure * weight
            local_sector_pressure += self._local_sector_pressure(point, profile) * weight

        rain_24h = sum((point.precipitation or 0.0) for point in history if start - point.time <= timedelta(hours=24))
        rain_72h = sum((point.precipitation or 0.0) for point in history)
        runoff_load = rain_24h + rain_72h * 0.5

        avg_wave = safe_avg([point.wave_height for point in target]) or 0.0
        max_wave = safe_max([point.wave_height for point in target]) or 0.0
        avg_wind = safe_avg([point.wind_speed for point in target]) or 0.0
        max_gust = safe_max([point.wind_gusts for point in target]) or 0.0
        avg_current = safe_avg([point.current_velocity for point in target]) or 0.0
        avg_temp = safe_avg([point.sea_temperature for point in target])
        avg_wave_period = safe_avg([point.wave_period for point in target]) or 4.0

        calm_hours = self._calm_hours(history, start, calm_wind_ms, calm_wave_m)
        calm_ratio = calm_hours / max(1.0, required_calm_hours)
        recovery_bonus = min(8.0, max(0.0, calm_ratio - 1.0) * 8.0 * water_exchange)
        recovery_penalty = max(0.0, 1.0 - calm_ratio) * 14.0 * sediment_risk * shallow_factor / max(0.65, water_exchange)

        sediment_memory_penalty = min(44.0, wind_factor * sediment_risk * shallow_factor * wind_memory * 0.13)
        historical_wave_penalty = min(28.0, wave_factor * sediment_risk * shallow_factor * wave_memory * 0.18)
        target_wave_penalty = (
            wave_factor
            * sediment_risk
            * shallow_factor
            * (avg_wave * 8.0 + max(0.0, max_wave - 0.45) * 18.0 + max(0.0, avg_wave_period - 5.0) * 0.9)
        )
        wind_penalty = wind_factor * (
            max(0.0, avg_wind - calm_wind_ms) * 3.1 + max(0.0, max_gust - (calm_wind_ms + 4.5)) * 1.15
        )
        runoff_penalty = rain_factor * runoff_sensitivity * min(24.0, runoff_load * 1.25)
        algae_penalty = algae_sensitivity * self._algae_risk(start.month, avg_temp) * 10.0

        dirty_current = self._direction_match_avg(target, "current_direction", profile.get("dirty_water_directions", []), tolerance)
        clear_current = self._direction_match_avg(target, "current_direction", profile.get("clear_water_directions", []), tolerance)
        current_penalty = (
            current_factor
            * current_sensitivity
            * (max(0.0, avg_current - 0.25) * 28.0 * sediment_risk + dirty_current * avg_current * 18.0)
        )
        clear_water_bonus = min(8.0, clear_current * avg_current * 20.0 * water_exchange)
        offshore_bonus = min(10.0, offshore_relief * 0.12 * water_exchange)
        local_penalty = min(16.0, local_sector_pressure * 1.2)

        base_score = self._float(profile.get("base_score"), self._fallback_base_score(spot))
        raw_score = (
            base_score
            + offshore_bonus
            + clear_water_bonus
            + recovery_bonus
            - sediment_memory_penalty
            - historical_wave_penalty
            - target_wave_penalty
            - wind_penalty
            - runoff_penalty
            - algae_penalty
            - current_penalty
            - recovery_penalty
            - local_penalty
        )
        score = round(clamp(raw_score, 0.0, 100.0))
        base_visibility = self._seasonal_visibility(spot, profile, start.month)
        estimated_visibility = self._visibility_estimate(score, base_visibility)
        grade = self._grade(score)
        confidence = self._confidence(profile, history, target, required_calm_hours)

        breakdown = {
            "base_score": round(base_score, 1),
            "sediment_penalty": round(sediment_memory_penalty + historical_wave_penalty + target_wave_penalty, 1),
            "wind_penalty": round(wind_penalty, 1),
            "runoff_penalty": round(runoff_penalty, 1),
            "algae_penalty": round(algae_penalty, 1),
            "current_penalty": round(current_penalty, 1),
            "recovery_modifier": round(recovery_bonus - recovery_penalty, 1),
            "clear_water_bonus": round(clear_water_bonus + offshore_bonus, 1),
            "local_penalty": round(local_penalty, 1),
        }

        reasons = self._reasons(
            score=score,
            profile=profile,
            breakdown=breakdown,
            onshore_wind_hours=onshore_wind_hours,
            avg_wind=avg_wind,
            max_gust=max_gust,
            avg_wave=avg_wave,
            max_wave=max_wave,
            rain_24h=rain_24h,
            rain_72h=rain_72h,
            avg_current=avg_current,
            calm_hours=calm_hours,
            required_calm_hours=required_calm_hours,
            offshore_bonus=offshore_bonus,
            clear_water_bonus=clear_water_bonus,
            local_penalty=local_penalty,
            algae_penalty=algae_penalty,
        )

        return {
            "label": label,
            "start": start.isoformat(timespec="minutes"),
            "end": end.isoformat(timespec="minutes"),
            "score": score,
            "grade": grade,
            "confidence": confidence,
            "estimated_visibility_m": estimated_visibility,
            "reasons": reasons,
            "breakdown": breakdown,
            "metrics": {
                "avg_wind_ms": round(avg_wind, 1),
                "max_gust_ms": round(max_gust, 1),
                "avg_wave_m": round(avg_wave, 2),
                "max_wave_m": round(max_wave, 2),
                "rain_24h_mm": round(rain_24h, 1),
                "rain_72h_mm": round(rain_72h, 1),
                "avg_current_ms": round(avg_current, 2),
                "calm_hours": round(calm_hours, 1),
                "required_calm_hours": round(required_calm_hours, 1),
                "sea_temperature_c": round(avg_temp, 1) if avg_temp is not None else None,
            },
        }

    def _profile(self, spot: dict[str, Any]) -> dict[str, Any]:
        profile = dict(spot.get("visibility_model") or {})
        if profile:
            return profile
        return {
            "base_score": self._fallback_base_score(spot),
            "spot_type": "Generisk kystspot",
            "bottom_type": "Ukendt bund",
            "depth_profile": "Ukendt dybdeprofil",
            "sediment_risk": 1.0,
            "shallow_factor": 1.0,
            "runoff_sensitivity": 1.0,
            "algae_sensitivity": 1.0,
            "current_sensitivity": 1.0,
            "water_exchange": 1.0,
            "required_calm_hours": 36.0,
            "calm_wind_ms": 4.8,
            "calm_wave_m": 0.35,
            "special_factors": ["Spottet bruger standardværdier, fordi der ikke er defineret en lokal profil endnu."],
        }

    def _fallback_base_score(self, spot: dict[str, Any]) -> float:
        visibility = self._float(spot.get("typical_visibility_m"), 4.0)
        bottom_bonus = self._float(spot.get("bottom_stability_bonus"), 0.0)
        return clamp(65.0 + visibility * 3.0 + bottom_bonus * 1.5, 45.0, 86.0)

    def _history_weight(self, age_hours: float) -> float:
        if age_hours <= 6:
            return 1.2
        if age_hours <= 24:
            return 1.0
        if age_hours <= 48:
            return 0.65
        return 0.35

    def _direction_factor(self, direction: float | None, sectors: list[dict[str, Any]], default: float) -> float:
        best = default
        for sector in sectors or []:
            match = direction_match(direction, [float(value) for value in sector.get("directions", [])], 55.0)
            if match > 0:
                factor = self._float(sector.get("factor"), default)
                best = max(best, default + (factor - default) * match)
        return best

    def _local_sector_pressure(self, point: HourlyPoint, profile: dict[str, Any]) -> float:
        pressure = 0.0
        wind = point.wind_speed or 0.0
        for sector in profile.get("local_penalty_sectors", []) or []:
            match = direction_match(point.wind_direction, [float(value) for value in sector.get("directions", [])], 50.0)
            pressure += match * self._float(sector.get("factor"), 1.0) * (wind / 6.0)
        return pressure

    def _direction_match_avg(
        self,
        points: list[HourlyPoint],
        attr: str,
        directions: list[float] | None,
        tolerance: float,
    ) -> float:
        if not points or not directions:
            return 0.0
        matches = [direction_match(getattr(point, attr), [float(value) for value in directions], tolerance) for point in points]
        return safe_avg(matches) or 0.0

    def _calm_hours(self, history: list[HourlyPoint], start: datetime, calm_wind_ms: float, calm_wave_m: float) -> float:
        calm_hours = 0.0
        for point in sorted((point for point in history if point.time <= start), key=lambda item: item.time, reverse=True):
            wind = point.wind_speed or 0.0
            wave = point.wave_height or 0.0
            rain = point.precipitation or 0.0
            if wind <= calm_wind_ms and wave <= calm_wave_m and rain <= 0.2:
                calm_hours += 1.0
                continue
            break
        return calm_hours

    def _algae_risk(self, month: int, sea_temperature: float | None) -> float:
        if month in (12, 1, 2, 3):
            risk = 0.12
        elif month in (4, 5):
            risk = 0.42
        elif month in (6, 7, 8):
            risk = 0.78
        elif month in (9, 10):
            risk = 0.58
        else:
            risk = 0.28
        if sea_temperature is not None:
            risk += clamp((sea_temperature - 12.0) / 18.0, 0.0, 0.22)
        return clamp(risk, 0.0, 1.0)

    def _seasonal_visibility(self, spot: dict[str, Any], profile: dict[str, Any], month: int) -> float:
        season = self._season(month)
        baselines = profile.get("baseline_visibility_m") or {}
        return self._float(baselines.get(season), self._float(spot.get("typical_visibility_m"), 4.0))

    def _season(self, month: int) -> str:
        if month in (12, 1, 2):
            return "winter"
        if month in (3, 4, 5):
            return "spring"
        if month in (6, 7, 8):
            return "summer"
        return "autumn"

    def _visibility_estimate(self, score: int, typical_visibility: float) -> dict[str, float]:
        low = clamp((score / 100.0) ** 1.35 * typical_visibility * 0.75, 0.1, typical_visibility * 1.15)
        high = clamp(low + typical_visibility * 0.42, 0.3, typical_visibility * 1.55)
        return {"low": round(low, 1), "high": round(high, 1)}

    def _grade(self, score: int) -> str:
        if score >= 80:
            return "Super"
        if score >= 62:
            return "Godt"
        if score >= 42:
            return "Måske"
        if score >= 25:
            return "Dårligt"
        return "Drop det"

    def _confidence(
        self,
        profile: dict[str, Any],
        history: list[HourlyPoint],
        target: list[HourlyPoint],
        required_calm_hours: float,
    ) -> dict[str, Any]:
        value = 0.78
        notes = []
        if not profile:
            value -= 0.15
            notes.append("Ingen lokal profil.")
        if len(history) < 48:
            value -= 0.12
            notes.append("Kort historik.")
        if required_calm_hours > 72:
            value -= 0.08
            notes.append("Spottet kræver længere ro end datavinduet kan dokumentere.")
        if not any(point.current_velocity is not None for point in target):
            value -= 0.08
            notes.append("Mangler strømdata.")
        if not any(point.wave_height is not None for point in target):
            value -= 0.12
            notes.append("Mangler bølgedata.")

        value = clamp(value, 0.35, 0.92)
        if value >= 0.74:
            label = "Høj"
        elif value >= 0.58:
            label = "Middel"
        else:
            label = "Lav"
        return {"value": round(value, 2), "label": label, "notes": notes}

    def _reasons(
        self,
        score: int,
        profile: dict[str, Any],
        breakdown: dict[str, float],
        onshore_wind_hours: float,
        avg_wind: float,
        max_gust: float,
        avg_wave: float,
        max_wave: float,
        rain_24h: float,
        rain_72h: float,
        avg_current: float,
        calm_hours: float,
        required_calm_hours: float,
        offshore_bonus: float,
        clear_water_bonus: float,
        local_penalty: float,
        algae_penalty: float,
    ) -> list[str]:
        reasons = []
        spot_type = profile.get("spot_type", "lokalt spot")
        bottom_type = profile.get("bottom_type", "ukendt bund")
        reasons.append(f"Lokal profil: {spot_type}; bund: {bottom_type}.")

        if breakdown["sediment_penalty"] > 24:
            reasons.append("Vind- og bølgeuro giver høj risiko for ophvirvlet sediment.")
        elif avg_wave < 0.3 and avg_wind < 5:
            reasons.append("Lav vind og lav bølgehøjde giver gode bundfældningsforhold.")
        elif onshore_wind_hours > 8:
            reasons.append("Der ligger stadig pålandskomponent i historikken.")

        if calm_hours < required_calm_hours * 0.55:
            reasons.append(f"Spottet har kun haft ca. {round(calm_hours)} rolige timer mod ønsket {round(required_calm_hours)}.")
        elif calm_hours >= required_calm_hours:
            reasons.append("Spottet har haft nok ro til at partikler kan bundfælde.")

        if avg_wave > 0.7 or max_wave > 0.9:
            reasons.append("Bølgehøjden er høj nok til at gøre lavt eller løst bundvand uklart.")
        elif avg_wave < 0.25:
            reasons.append("Meget lav bølgehøjde trækker vurderingen op.")

        if avg_wind > 7 or max_gust > 11:
            reasons.append("Vind eller vindstød i perioden kan holde overflade og bund i uro.")

        if rain_24h > 8 or rain_72h > 18:
            reasons.append("Regn/runoff vægtes lokalt, især nær havne, åer, dræn eller fjorde.")

        if algae_penalty > 7:
            reasons.append("Sæson og vandtemperatur giver forhøjet algerisiko.")

        if avg_current > 0.42:
            reasons.append("Strømmen er frisk nok til at transportere klart eller uklart vand ind over spottet.")

        if clear_water_bonus + offshore_bonus > 4:
            reasons.append("Fralandsvind eller klar vandtransport hjælper vurderingen.")

        if local_penalty > 3:
            reasons.append("En lokal specialregel er aktiv for dette spot.")

        if score < 35:
            reasons.append("Samlet vurdering: vælg et mere lægivende eller mere robust spot.")
        return reasons[:6]

    def _float(self, value: Any, fallback: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return fallback
