import uuid
from typing import Optional, Dict, Any


class Puzzle:
    def __init__(self, db):
        self.db = db
        self._row = None
        self._seed_norm = None

    def _normalize_uuid(self, seed: str) -> Optional[str]:
        s = (seed or "").strip()
        if not s:
            return None
        try:
            return str(uuid.UUID(s)) 
        except Exception:
            return None

    def checkSeed(self, seed: str) -> bool:
        norm = self._normalize_uuid(seed)
        if not norm:
            self._row = None
            self._seed_norm = None
            return False

        self._seed_norm = norm
        self._row = self.db.get_puzzle_by_seed(norm)
        return self._row is not None

    def displayPuzzle(self) -> Optional[Dict[str, Any]]:
        if not self._row:
            return None

        return {
            "seed": self._row["seed"],
            "puzzle_data": self._row["puzzle_data"],
            "difficulty": self._row["difficulty"],
            "campaign_level": self._row["campaign_level"],
        }