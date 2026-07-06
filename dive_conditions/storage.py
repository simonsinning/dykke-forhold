from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any


class SpotStore:
    def __init__(self, path: Path):
        self.path = path

    def all(self) -> list[dict[str, Any]]:
        with self.path.open("r", encoding="utf-8") as file:
            return json.load(file)

    def get(self, spot_id: str) -> dict[str, Any] | None:
        return next((spot for spot in self.all() if spot["id"] == spot_id), None)


class ObservationStore:
    FIELDS = ["created_at", "spot_id", "visibility_m", "surface", "diveable", "notes"]

    def __init__(self, path: Path):
        self.path = path

    def add(self, payload: dict[str, Any]) -> dict[str, Any]:
        spot_id = str(payload.get("spot_id", "")).strip()
        if not spot_id:
            raise ValueError("spot_id mangler")

        try:
            visibility = float(payload.get("visibility_m", ""))
        except (TypeError, ValueError):
            raise ValueError("Sigtbarhed skal være et tal")

        if visibility < 0 or visibility > 30:
            raise ValueError("Sigtbarhed skal være mellem 0 og 30 meter")

        row = {
            "created_at": datetime.now().isoformat(timespec="minutes"),
            "spot_id": spot_id,
            "visibility_m": visibility,
            "surface": str(payload.get("surface", "")).strip(),
            "diveable": "ja" if bool(payload.get("diveable", True)) else "nej",
            "notes": str(payload.get("notes", "")).strip(),
        }
        self._ensure_file()
        with self.path.open("a", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=self.FIELDS)
            writer.writerow(row)
        return row

    def recent_for_spot(self, spot_id: str, limit: int = 25) -> list[dict[str, Any]]:
        self._ensure_file()
        with self.path.open("r", newline="", encoding="utf-8") as file:
            rows = list(csv.DictReader(file))
        if spot_id:
            rows = [row for row in rows if row.get("spot_id") == spot_id]
        rows.sort(key=lambda row: row.get("created_at", ""), reverse=True)
        return rows[:limit]

    def _ensure_file(self):
        self.path.parent.mkdir(exist_ok=True)
        if self.path.exists():
            return
        with self.path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=self.FIELDS)
            writer.writeheader()
