class Leaderboard:
    def __init__(self, db):
        self.db = db

    def setPuzzleLeaderboard(self, user_id: int, seed: str, elapsed_time: float):
        user_row = self.db.getUserInfo(user_id)
        puzzle_row = self.db.getPuzzleInfo(seed)

        if not user_row or not puzzle_row:
            return []

        rows = self.db.compareTime(user_id, seed, float(elapsed_time)) or []
        return sorted(rows, key=lambda row: (float(row["elapsed_time"]), str(row["username"])))