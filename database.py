import sqlite3
import os


class Database:
    def __init__(self, db_name="kakuro.db", db_path=None):
        if db_path:
            self.db_path = db_path
        else:
            self.db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), db_name)

    def get_connection(self):
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON;")
        return con

    def create_tables(self):
        con = self.get_connection()
        cur = con.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS progression (
                user_id INTEGER PRIMARY KEY,
                mode TEXT NOT NULL DEFAULT 'Campaign',
                campaign_level INTEGER NOT NULL DEFAULT 1,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS puzzles (
                seed TEXT PRIMARY KEY,
                puzzle_data TEXT NOT NULL,
                difficulty TEXT,
                campaign_level INTEGER
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS puzzle_solutions (
                seed TEXT PRIMARY KEY,
                solution_data TEXT NOT NULL,
                FOREIGN KEY(seed) REFERENCES puzzles(seed) ON DELETE CASCADE
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_puzzles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                seed TEXT NOT NULL,
                played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, seed),
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(seed) REFERENCES puzzles(seed) ON DELETE CASCADE
            )
        """)


        con.commit()
        con.close()

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
            (username, email, password_hash)
        )
        con.commit()
        user_id = cur.lastrowid
        con.close()
        return user_id

    # Progression
    def ensure_progression_row(self, user_id: int):
        con = self.get_connection()
        cur = con.cursor()
        cur.execute("SELECT user_id FROM progression WHERE user_id = ?", (user_id,))
        exists = cur.fetchone()
        if not exists:
            cur.execute(
                "INSERT INTO progression (user_id, mode, campaign_level) VALUES (?, 'Campaign', 1)",
                (user_id,)
            )
            con.commit()
        con.close()

    def set_mode(self, user_id: int, mode: str):
        con = self.get_connection()
        cur = con.cursor()
        cur.execute("""
            UPDATE progression
            SET mode = ?, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        """, (mode, user_id))
        con.commit()
        con.close()

    def set_campaign_level(self, user_id: int, level: int):
        con = self.get_connection()
        cur = con.cursor()
        cur.execute("""
            UPDATE progression
            SET campaign_level = ?, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        """, (level, user_id))
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

    def mark_user_played_seed(self, user_id: int, seed: str):
        con = self.get_connection()
        cur = con.cursor()
        cur.execute(
            "INSERT OR IGNORE INTO user_puzzles (user_id, seed) VALUES (?, ?)",
            (user_id, seed)
        )
        con.commit()
        con.close()

    # Inserts a puzzle row into puzzles table (no solution in puzzle_data).
    def insert_puzzle(self, seed: str, puzzle_data: str, difficulty: str, campaign_level: int) -> None:
        con = self.get_connection()
        cur = con.cursor()
        cur.execute(
            "INSERT INTO puzzles (seed, puzzle_data, difficulty, campaign_level) VALUES (?, ?, ?, ?)",
            (seed, puzzle_data, difficulty, campaign_level)
        )
        con.commit()
        con.close()

    # Inserts the solution JSON into puzzle_solutions (never exposed by API).
    def insert_puzzle_solution(self, seed: str, solution_data: str) -> None:
        con = self.get_connection()
        cur = con.cursor()
        cur.execute(
            "INSERT INTO puzzle_solutions (seed, solution_data) VALUES (?, ?)",
            (seed, solution_data)
        )
        con.commit()
        con.close()