from typing import Optional, Dict, Any
import re


class Puzzle:
    def __init__(self, db):
        self.db = db
        self._row = None
        self._seed_norm = None

    # Normalize and validate a seed code.
    # Rule: exactly 6 chars, lowercase letters + digits only (0-9, a-z).
    def _normalize_seed(self, seed: str) -> Optional[str]:
        s = (seed or "").strip().lower()
        if not s:
            return None
        if re.fullmatch(r"[0-9a-z]{6}", s) is None:
            return None
        return s

    def checkSeed(self, seed: str) -> bool:
        norm = self._normalize_seed(seed)
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