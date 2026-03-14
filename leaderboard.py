class Leaderboard:
    def __init__(self, db):
        self.db = db
        self.seed = None
        self.elapsed_time = None

    def setSeed(self, seed: str):
        self.seed = seed
        return self.seed

    def setElapsedTime(self, elapsed_time: float):
        self.elapsed_time = float(elapsed_time)
        return self.elapsed_time

    def sortLeaderboard(self, rows):
        return sorted(rows, key=lambda row: (float(row["elapsed_time"]), str(row["username"])))

    def setPuzzleLeaderboard(self, user_id: int, seed: str, elapsed_time: float):
        user_row = self.db.getUserInfo(user_id)
        puzzle_row = self.db.getPuzzleInfo(seed)
        if not user_row or not puzzle_row:
            return []

        self.setSeed(seed)
        self.setElapsedTime(elapsed_time)
        rows = self.db.compareTime(user_id, self.seed, self.elapsed_time) or []
        return self.sortLeaderboard(rows)