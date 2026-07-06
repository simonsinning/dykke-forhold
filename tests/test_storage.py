from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from dive_conditions.storage import ObservationStore


class ObservationStoreTest(unittest.TestCase):
    def test_add_and_read_observation(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ObservationStore(Path(tmp) / "observations.csv")
            saved = store.add(
                {
                    "spot_id": "sletten",
                    "visibility_m": "3.2",
                    "surface": "roligt",
                    "diveable": True,
                    "notes": "fin sigt over tang",
                }
            )

            rows = store.recent_for_spot("sletten")

            self.assertEqual(saved["spot_id"], "sletten")
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["visibility_m"], "3.2")

    def test_rejects_invalid_visibility(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ObservationStore(Path(tmp) / "observations.csv")
            with self.assertRaises(ValueError):
                store.add({"spot_id": "sletten", "visibility_m": "klart"})


if __name__ == "__main__":
    unittest.main()
