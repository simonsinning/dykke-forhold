from __future__ import annotations

import json
import os
from datetime import datetime
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from dive_conditions.data_provider import OpenMeteoProvider
from dive_conditions.scoring import ScoreEngine
from dive_conditions.storage import ObservationStore, SpotStore


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
DATA_DIR = BASE_DIR / "data"

RANKING_GROUPS = [
    {"label": "I dag", "ratings": ["Nu", "I aften"]},
    {"label": "I morgen", "ratings": ["I morgen"]},
    {"label": "Om 2 dage", "ratings": ["Om 2 dage"]},
]


class DiveConditionsHandler(SimpleHTTPRequestHandler):
    provider = OpenMeteoProvider()
    spots = SpotStore(DATA_DIR / "spots.json")
    observations = ObservationStore(DATA_DIR / "observations.csv")
    scorer = ScoreEngine()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/spots":
            return self._send_json({"spots": self.spots.all()})

        if parsed.path == "/api/score":
            query = parse_qs(parsed.query)
            spot_id = query.get("spot", [""])[0]
            spot = self.spots.get(spot_id)
            if not spot:
                return self._send_json({"error": "Ukendt spot"}, HTTPStatus.NOT_FOUND)

            forecast = self.provider.fetch(spot["latitude"], spot["longitude"])
            score = self.scorer.score_spot(spot, forecast)
            recent_observations = self.observations.recent_for_spot(spot_id, limit=8)
            return self._send_json(
                {
                    "spot": spot,
                    "forecast": forecast.summary(),
                    "series": forecast.series(),
                    "score": score,
                    "observations": recent_observations,
                }
            )

        if parsed.path == "/api/rankings":
            return self._send_json(self._rankings_payload())

        if parsed.path == "/api/observations":
            query = parse_qs(parsed.query)
            spot_id = query.get("spot", [""])[0]
            return self._send_json({"observations": self.observations.recent_for_spot(spot_id)})

        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/api/observations":
            return self._send_json({"error": "Ikke fundet"}, HTTPStatus.NOT_FOUND)

        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            saved = self.observations.add(payload)
        except ValueError as exc:
            return self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

        return self._send_json({"observation": saved}, HTTPStatus.CREATED)

    def _send_json(self, payload, status=HTTPStatus.OK):
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _rankings_payload(self):
        days = [{"label": group["label"], "rankings": []} for group in RANKING_GROUPS]
        warnings = []

        for spot in self.spots.all():
            forecast = self.provider.fetch(spot["latitude"], spot["longitude"])
            score = self.scorer.score_spot(spot, forecast)
            ratings_by_label = {rating["label"]: rating for rating in score["ratings"]}
            warnings.extend(forecast.warnings)

            for index, group in enumerate(RANKING_GROUPS):
                candidates = [ratings_by_label[label] for label in group["ratings"] if label in ratings_by_label]
                if not candidates:
                    continue
                rating = max(candidates, key=lambda item: item["score"])
                days[index]["rankings"].append(
                    {
                        "spot_id": spot["id"],
                        "name": spot["name"],
                        "area": spot["area"],
                        "latitude": spot["latitude"],
                        "longitude": spot["longitude"],
                        "score": rating["score"],
                        "grade": rating["grade"],
                        "window": rating["label"],
                        "start": rating["start"],
                        "end": rating["end"],
                        "estimated_visibility_m": rating["estimated_visibility_m"],
                        "metrics": rating["metrics"],
                        "reasons": rating["reasons"][:2],
                    }
                )

        for day in days:
            day["rankings"].sort(key=lambda item: item["score"], reverse=True)
            for rank, item in enumerate(day["rankings"], start=1):
                item["rank"] = rank

        return {
            "generated_at": datetime.now().isoformat(timespec="minutes"),
            "days": days,
            "warnings": sorted(set(warnings)),
        }


def main():
    DATA_DIR.mkdir(exist_ok=True)
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8765"))
    server = ThreadingHTTPServer((host, port), DiveConditionsHandler)
    display_host = "127.0.0.1" if host in {"0.0.0.0", ""} else host
    print(f"Dykke forhold kører på http://{display_host}:{port}")
    print("Tryk Ctrl+C for at stoppe.")
    server.serve_forever()


if __name__ == "__main__":
    main()
