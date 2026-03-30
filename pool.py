import random


class Pool:
    def __init__(self, db, rng=None):
        self.db = db
        self.rng = rng or random

    def getRandomPuzzle(self, difficulty: str, level: int, excluded_seeds=None):
        rows = list(
            self.db.getPuzzleSkill(difficulty, int(level)) or []
        )
        if not rows:
            return None

        excluded = set(excluded_seeds or [])
        filtered = [row for row in rows if row["seed"] not in excluded]
        choices = filtered if filtered else rows
        picked = self.rng.choice(choices)
        return picked["seed"]