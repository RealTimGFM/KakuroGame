import json
import os
import sqlite3
import sys


class Database:
    def __init__(self, db_name="kakuro.db", db_path=None):
        if db_path:
            self.db_path = db_path
        else:
            self.db_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), db_name
            )

    def get_connection(self):
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON;")
        return con

    def _ensure_column(self, table_name: str, column_name: str, column_sql: str):
        con = self.get_connection()
        cur = con.cursor()
        cur.execute(f"PRAGMA table_info({table_name})")
        cols = [row["name"] for row in cur.fetchall()]
        if column_name not in cols:
            cur.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_sql}")
            con.commit()
        con.close()

    def create_tables(self):
        con = self.get_connection()
        cur = con.cursor()

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS progression (
                user_id INTEGER PRIMARY KEY,
                mode TEXT NOT NULL DEFAULT 'Campaign',
                difficulty TEXT NOT NULL DEFAULT 'Learner',
                campaign_level INTEGER NOT NULL DEFAULT 1,
                campaign_ineligible INTEGER NOT NULL DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS puzzles (
                seed TEXT PRIMARY KEY,
                puzzle_data TEXT NOT NULL,
                difficulty TEXT,
                campaign_level INTEGER
            )
        """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS puzzle_solutions (
                seed TEXT PRIMARY KEY,
                solution_data TEXT NOT NULL,
                FOREIGN KEY(seed) REFERENCES puzzles(seed) ON DELETE CASCADE
            )
        """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS user_puzzles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                seed TEXT NOT NULL,
                played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                solution_shown INTEGER NOT NULL DEFAULT 0,
                UNIQUE(user_id, seed),
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(seed) REFERENCES puzzles(seed) ON DELETE CASCADE
            )
        """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS leaderboard (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                seed TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                username TEXT NOT NULL,
                elapsed_time REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(seed, user_id),
                FOREIGN KEY(seed) REFERENCES puzzles(seed) ON DELETE CASCADE,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS campaign_leaderboard (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                username TEXT NOT NULL,
                elapsed_time REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """
        )
        con.commit()
        con.close()

        # Safe small migrations for older DB files
        # Safe small migrations for older DB files
        self._ensure_column("user_puzzles", "completed_at", "completed_at TIMESTAMP")
        self._ensure_column(
            "user_puzzles", "last_elapsed_time", "last_elapsed_time REAL"
        )
        self._ensure_column(
            "user_puzzles", "best_elapsed_time", "best_elapsed_time REAL"
        )
        self._ensure_column(
            "progression", "difficulty", "difficulty TEXT NOT NULL DEFAULT 'Learner'"
        )
        self._ensure_column(
            "progression",
            "campaign_ineligible",
            "campaign_ineligible INTEGER NOT NULL DEFAULT 0",
        )
        self._ensure_column(
            "user_puzzles",
            "solution_shown",
            "solution_shown INTEGER NOT NULL DEFAULT 0",
        )

    # Users
    def get_user_by_username(self, username: str):
        con = self.get_connection()
        cur = con.cursor()
        cur.execute("SELECT * FROM users WHERE username = ?", (username,))
        row = cur.fetchone()
        con.close()
        return row

    def get_user_by_email(self, email: str):
        con = self.get_connection()
        cur = con.cursor()
        cur.execute("SELECT * FROM users WHERE email = ?", (email,))
        row = cur.fetchone()
        con.close()
        return row

    def create_user(self, username: str, email: str, password_hash: str) -> int:
        con = self.get_connection()
        cur = con.cursor()
        cur.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
            (username, email, password_hash),
        )
        con.commit()
        user_id = cur.lastrowid
        con.close()
        return user_id

    def getUserInfo(self, user_id: int):
        con = self.get_connection()
        cur = con.cursor()
        cur.execute("SELECT id, username, email FROM users WHERE id = ?", (user_id,))
        row = cur.fetchone()
        con.close()
        return row

    # Progression
    def ensure_progression_row(self, user_id: int):
        con = self.get_connection()
        cur = con.cursor()
        cur.execute("SELECT user_id FROM progression WHERE user_id = ?", (user_id,))
        exists = cur.fetchone()
        if not exists:
            cur.execute(
                "INSERT INTO progression (user_id, mode, difficulty, campaign_level) VALUES (?, 'Campaign', 'Learner', 1)",
                (user_id,),
            )
            con.commit()
        con.close()

    def set_mode(self, user_id: int, mode: str):
        con = self.get_connection()
        cur = con.cursor()
        cur.execute(
            """
            UPDATE progression
            SET mode = ?, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        """,
            (mode, user_id),
        )
        con.commit()
        con.close()

    def set_difficulty(self, user_id: int, difficulty: str):
        con = self.get_connection()
        cur = con.cursor()
        cur.execute(
            """
            UPDATE progression
            SET difficulty = ?, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        """,
            (difficulty, user_id),
        )
        con.commit()
        con.close()

    def set_campaign_level(self, user_id: int, level: int):
        con = self.get_connection()
        cur = con.cursor()
        cur.execute(
            """
            UPDATE progression
            SET campaign_level = ?, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        """,
            (level, user_id),
        )
        con.commit()
        con.close()

    def get_progression(self, user_id: int):
        con = self.get_connection()
        cur = con.cursor()
        cur.execute("SELECT * FROM progression WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        con.close()
        return row

    # Puzzles
    def get_puzzle_by_seed(self, seed: str):
        con = self.get_connection()
        cur = con.cursor()
        cur.execute("SELECT * FROM puzzles WHERE seed = ?", (seed,))
        row = cur.fetchone()
        con.close()
        return row

    def getPuzzleInfo(self, seed: str):
        return self.get_puzzle_by_seed(seed)

    def get_puzzle_solution(self, seed: str):
        con = self.get_connection()
        cur = con.cursor()
        cur.execute("SELECT * FROM puzzle_solutions WHERE seed = ?", (seed,))
        row = cur.fetchone()
        con.close()
        return row

    def getPuzzleSkill(self, difficulty: str, level: int):
        con = self.get_connection()
        cur = con.cursor()
        cur.execute(
            """
            SELECT seed, puzzle_data, difficulty, campaign_level
            FROM puzzles
            WHERE difficulty = ? AND campaign_level = ?
            ORDER BY seed ASC
            """,
            (difficulty, int(level)),
        )
        rows = cur.fetchall()
        con.close()
        return rows

    def get_max_campaign_level_for_difficulty(self, difficulty: str) -> int:
        con = self.get_connection()
        cur = con.cursor()
        cur.execute(
            "SELECT COALESCE(MAX(campaign_level), 0) AS max_level FROM puzzles WHERE difficulty = ?",
            (difficulty,),
        )
        row = cur.fetchone()
        con.close()
        return int(row["max_level"] if row and row["max_level"] is not None else 0)

    def mark_user_played_seed(self, user_id: int, seed: str):
        con = self.get_connection()
        cur = con.cursor()
        cur.execute(
            "INSERT OR IGNORE INTO user_puzzles (user_id, seed) VALUES (?, ?)",
            (user_id, seed),
        )
        con.commit()
        con.close()

    def insert_puzzle(
        self, seed: str, puzzle_data: str, difficulty: str, campaign_level: int
    ) -> None:
        con = self.get_connection()
        cur = con.cursor()
        cur.execute(
            "INSERT INTO puzzles (seed, puzzle_data, difficulty, campaign_level) VALUES (?, ?, ?, ?)",
            (seed, puzzle_data, difficulty, campaign_level),
        )
        con.commit()
        con.close()

    def insert_puzzle_solution(self, seed: str, solution_data: str) -> None:
        con = self.get_connection()
        cur = con.cursor()
        cur.execute(
            "INSERT INTO puzzle_solutions (seed, solution_data) VALUES (?, ?)",
            (seed, solution_data),
        )
        con.commit()
        con.close()

    def _build_digits_from_board(self, puzzle_data_str: str, board: dict) -> str:
        pd = json.loads(puzzle_data_str)
        w = pd["w"]
        h = pd["h"]
        mask = pd["mask"]

        out = []
        for i in range(w * h):
            if mask[i] == "0":
                out.append(str(board.get(str(i), ".")))
            else:
                out.append(".")
        return "".join(out)

    def isCompleted(self, seed: str, board: dict) -> bool:
        puzzle_row = self.get_puzzle_by_seed(seed)
        solution_row = self.get_puzzle_solution(seed)
        if not puzzle_row or not solution_row:
            return False

        try:
            current_digits = self._build_digits_from_board(
                puzzle_row["puzzle_data"], board
            )
            solution_obj = json.loads(solution_row["solution_data"])
            return current_digits == solution_obj.get("digits", "")
        except Exception:
            return False

    def update(self, user_id: int, seed: str, elapsed_time: float):
        self.mark_user_played_seed(user_id, seed)

        con = self.get_connection()
        cur = con.cursor()
        cur.execute(
            "SELECT best_elapsed_time FROM user_puzzles WHERE user_id = ? AND seed = ?",
            (user_id, seed),
        )
        row = cur.fetchone()

        best_time = float(elapsed_time)
        if row and row["best_elapsed_time"] is not None:
            best_time = min(float(row["best_elapsed_time"]), float(elapsed_time))

        cur.execute(
            """
            UPDATE user_puzzles
            SET completed_at = CURRENT_TIMESTAMP,
                last_elapsed_time = ?,
                best_elapsed_time = ?
            WHERE user_id = ? AND seed = ?
        """,
            (float(elapsed_time), best_time, user_id, seed),
        )
        con.commit()
        con.close()

    def compareTime(self, user_id: int, seed: str, elapsed_time: float):
        user_row = self.getUserInfo(user_id)
        if not user_row:
            return None

        con = self.get_connection()
        cur = con.cursor()
        cur.execute(
            "SELECT * FROM leaderboard WHERE user_id = ? AND seed = ?", (user_id, seed)
        )
        row = cur.fetchone()

        if row is None:
            cur.execute(
                """
                INSERT INTO leaderboard (seed, user_id, username, elapsed_time)
                VALUES (?, ?, ?, ?)
            """,
                (seed, user_id, user_row["username"], float(elapsed_time)),
            )
        else:
            keep_time = min(float(row["elapsed_time"]), float(elapsed_time))
            cur.execute(
                """
                UPDATE leaderboard
                SET username = ?, elapsed_time = ?, updated_at = CURRENT_TIMESTAMP
                WHERE seed = ? AND user_id = ?
            """,
                (user_row["username"], keep_time, seed, user_id),
            )

        con.commit()
        con.close()
        return self.get_leaderboard_by_seed(seed)

    def get_leaderboard_by_seed(self, seed: str):
        con = self.get_connection()
        cur = con.cursor()
        cur.execute(
            """
            SELECT seed, user_id, username, elapsed_time
            FROM leaderboard
            WHERE seed = ?
            ORDER BY elapsed_time ASC, username ASC
        """,
            (seed,),
        )
        rows = cur.fetchall()
        con.close()
        return rows

    def compareCampaignTime(self, user_id: int, elapsed_time: float):
        user_row = self.getUserInfo(user_id)
        if not user_row:
            return None

        con = self.get_connection()
        cur = con.cursor()
        cur.execute("SELECT * FROM campaign_leaderboard WHERE user_id = ?", (user_id,))
        row = cur.fetchone()

        if row is None:
            cur.execute(
                "INSERT INTO campaign_leaderboard (user_id, username, elapsed_time) VALUES (?, ?, ?)",
                (user_id, user_row["username"], float(elapsed_time)),
            )
        else:
            keep_time = min(float(row["elapsed_time"]), float(elapsed_time))
            cur.execute(
                """
                UPDATE campaign_leaderboard
                SET username = ?, elapsed_time = ?, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            """,
                (user_row["username"], keep_time, user_id),
            )

        con.commit()
        con.close()
        return self.get_campaign_leaderboard()

    def get_campaign_leaderboard(self):
        con = self.get_connection()
        cur = con.cursor()
        cur.execute(
            """
            SELECT user_id, username, elapsed_time
            FROM campaign_leaderboard
            ORDER BY elapsed_time ASC, username ASC
        """
        )
        rows = cur.fetchall()
        con.close()
        return rows


def init_db_only():
    db = Database()
    db.create_tables()
    print(f"database ready: {db.db_path}")


def load_puzzles(import_path=None):
    from puzzle_importer import import_puzzles_from_file

    db = Database()
    db.create_tables()

    if import_path is None:
        import_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "puzzles_import.json"
        )

    if not os.path.exists(import_path):
        print(f"import file not found: {import_path}")
        return

    import_puzzles_from_file(db, import_path)
    print(f"puzzle import finished from: {import_path}")


def reset_db(import_path=None):
    from puzzle_importer import import_puzzles_from_file

    db = Database()

    if os.path.exists(db.db_path):
        os.remove(db.db_path)
        print(f"old database deleted: {db.db_path}")
    else:
        print("no old database found, creating a new one")

    db.create_tables()
    print(f"new database created: {db.db_path}")

    if import_path is None:
        import_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "puzzles_import.json"
        )

    if not os.path.exists(import_path):
        print(f"import file not found: {import_path}")
        print("database was reset, but no puzzles were imported")
        return

    import_puzzles_from_file(db, import_path)
    print(f"database reset complete and puzzles imported from: {import_path}")


if __name__ == "__main__":
    # Usage:
    # python database.py Create tables + import default puzzles
    # python database.py init Create tables only
    # python database.py load Create tables + import default puzzles
    # python database.py load puzzles_import.json Import puzzles from a custom file
    # python database.py reset
    # python database.py reset puzzles_import.json
    cmd = "load"
    import_path = None

    if len(sys.argv) >= 2:
        cmd = sys.argv[1].strip().lower()

    if len(sys.argv) >= 3:
        import_path = sys.argv[2]

    if cmd == "init":
        init_db_only()
    elif cmd == "load":
        load_puzzles(import_path)
    elif cmd == "reset":
        reset_db(import_path)
    else:
        print("unknown command")
        print("usage:")
        print("  python database.py")
        print("  python database.py init")
        print("  python database.py load")
        print("  python database.py load puzzles_import.json")
        print("  python database.py reset")
        print("  python database.py reset puzzles_import.json")
