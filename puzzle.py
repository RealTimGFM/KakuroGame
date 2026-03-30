from typing import Optional, Dict, Any
import re
import time
from flask import session
from cell import Cell
from validator import Validator


class Puzzle:
    def __init__(self, db):
        self.db = db
        self._row = None
        self._seed_norm = None

    def checkSeed(self, seed: str) -> bool:
        s = (seed or "").strip().lower()

        if not s:
            self._row = None
            self._seed_norm = None
            return False

        if re.fullmatch(r"[0-9a-z]{6}", s) is None:
            self._row = None
            self._seed_norm = None
            return False

        self._seed_norm = s
        self._row = self.db.get_puzzle_by_seed(s)
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

    def loadPuzzle(self, seed: str) -> Optional[Dict[str, Any]]:
        if not self.checkSeed(seed):
            return None

        session.pop("seeded_puzzle_board", None)
        session.pop("seeded_puzzle_invalid_positions", None)
        session.pop("seeded_puzzle_locked", None)
        session.pop("seeded_puzzle_started_at", None)
        session.pop("seeded_puzzle_stopped_at", None)
        session.pop("seeded_puzzle_elapsed_time", None)
        session.pop("seeded_puzzle_result", None)
        session.pop("seeded_puzzle_result_type", None)

        payload = self.displayPuzzle()
        if payload is None:
            return None

        session["seeded_puzzle_seed"] = payload["seed"]
        session["seeded_puzzle_started_at"] = time.time()
        return payload

    def isLocked(self) -> bool:
        if session.get("seeded_puzzle_locked") is None:
            session["seeded_puzzle_locked"] = False
        return session.get("seeded_puzzle_locked", False) is True

    def getPlaySummary(self) -> Dict[str, Any]:
        board = session.get("seeded_puzzle_board")
        if not isinstance(board, dict):
            board = {}
            session["seeded_puzzle_board"] = board

        invalid_positions = session.get("seeded_puzzle_invalid_positions")
        if not isinstance(invalid_positions, list):
            invalid_positions = []
            session["seeded_puzzle_invalid_positions"] = invalid_positions

        if session.get("seeded_puzzle_locked") is None:
            session["seeded_puzzle_locked"] = False

        if session.get("seeded_puzzle_started_at") is None:
            session["seeded_puzzle_started_at"] = time.time()

        return {
            "board": dict(board),
            "invalid_positions": list(invalid_positions),
            "locked": session.get("seeded_puzzle_locked", False) is True,
            "result": session.get("seeded_puzzle_result"),
            "result_type": session.get("seeded_puzzle_result_type"),
            "elapsed_time": session.get("seeded_puzzle_elapsed_time"),
        }

    def fillCells(self, position, value):
        board = session.get("seeded_puzzle_board")
        if not isinstance(board, dict):
            board = {}
            session["seeded_puzzle_board"] = board

        invalid_positions = session.get("seeded_puzzle_invalid_positions")
        if not isinstance(invalid_positions, list):
            invalid_positions = []
            session["seeded_puzzle_invalid_positions"] = invalid_positions

        if session.get("seeded_puzzle_locked") is None:
            session["seeded_puzzle_locked"] = False

        if session.get("seeded_puzzle_started_at") is None:
            session["seeded_puzzle_started_at"] = time.time()

        if session.get("seeded_puzzle_locked", False) is True:
            return {
                "ok": False,
                "error": "Puzzle is locked.",
                "invalid_positions": [],
                "locked": True,
            }

        if not self._row:
            seed = session.get("seeded_puzzle_seed")
            if not seed or not self.checkSeed(seed):
                return {
                    "ok": False,
                    "error": "seed not found",
                    "invalid_positions": [],
                    "locked": False,
                }

        cell = Cell(position, board)
        clean_value = "" if value is None else str(value).strip()

        validator = Validator.create(
            self._row["puzzle_data"],
            cell.position,
            clean_value,
            board,
        )
        validator.checkInput()

        cell.setValue(clean_value)
        session["seeded_puzzle_board"] = board

        cell.invalid_positions = validator.locateErrorInput()
        invalid_positions = cell.highlightCell()

        session["seeded_puzzle_invalid_positions"] = invalid_positions

        if session.get("seeded_puzzle_result_type") != "success":
            session.pop("seeded_puzzle_result", None)
            session.pop("seeded_puzzle_result_type", None)

        return {
            "ok": True,
            "position": cell.position,
            "value": board.get(str(cell.position), ""),
            "invalid_positions": invalid_positions,
            "locked": False,
        }

    def lockPuzzle(self):
        if session.get("seeded_puzzle_locked") is None:
            session["seeded_puzzle_locked"] = False
        session["seeded_puzzle_locked"] = True

    def stopTimer(self):
        if session.get("seeded_puzzle_started_at") is None:
            session["seeded_puzzle_started_at"] = time.time()

        if session.get("seeded_puzzle_stopped_at") is None:
            session["seeded_puzzle_stopped_at"] = time.time()

    def calculateTime(self):
        if session.get("seeded_puzzle_started_at") is None:
            session["seeded_puzzle_started_at"] = time.time()

        start = session.get("seeded_puzzle_started_at")
        stop = session.get("seeded_puzzle_stopped_at")

        if stop is None:
            stop = time.time()
            session["seeded_puzzle_stopped_at"] = stop

        elapsed = round(max(0.0, float(stop) - float(start)), 2)
        session["seeded_puzzle_elapsed_time"] = elapsed
        return elapsed

    def displayResult(self, done: bool, elapsed_time: Optional[float] = None):
        if done:
            msg = "Puzzle completed!"
            if elapsed_time is not None:
                msg = f"Puzzle completed in {elapsed_time:.2f}s!"
            session["seeded_puzzle_result"] = msg
            session["seeded_puzzle_result_type"] = "success"
            return msg

        msg = "Puzzle is not complete yet."
        session["seeded_puzzle_result"] = msg
        session["seeded_puzzle_result_type"] = "error"
        return msg

    def checkPuzzle(self, progression=None):
        board = session.get("seeded_puzzle_board")
        if not isinstance(board, dict):
            board = {}
            session["seeded_puzzle_board"] = board

        invalid_positions = session.get("seeded_puzzle_invalid_positions")
        if not isinstance(invalid_positions, list):
            invalid_positions = []
            session["seeded_puzzle_invalid_positions"] = invalid_positions

        if session.get("seeded_puzzle_locked") is None:
            session["seeded_puzzle_locked"] = False

        if session.get("seeded_puzzle_started_at") is None:
            session["seeded_puzzle_started_at"] = time.time()

        if not self._row:
            seed = session.get("seeded_puzzle_seed")
            if not seed or not self.checkSeed(seed):
                return {"done": False, "error": "seed not found", "leaderboard": []}

        seed = self._row["seed"]

        invalid_positions = []
        seen = set()

        for key, raw in board.items():
            try:
                position = int(key)
            except Exception:
                continue

            validator = Validator.create(self._row["puzzle_data"], position, raw, board)

            if not validator.checkInput():
                for bad_pos in validator.locateErrorInput():
                    if bad_pos not in seen:
                        seen.add(bad_pos)
                        invalid_positions.append(bad_pos)

        invalid_positions.sort()
        session["seeded_puzzle_invalid_positions"] = invalid_positions

        if invalid_positions:
            session["seeded_puzzle_result"] = "Puzzle has invalid input."
            session["seeded_puzzle_result_type"] = "error"

            return {
                "done": False,
                "locked": False,
                "elapsed_time": session.get("seeded_puzzle_elapsed_time"),
                "result": session.get("seeded_puzzle_result"),
                "leaderboard": [],
            }

        done = self.db.isCompleted(seed, board)

        if done:
            session["seeded_puzzle_invalid_positions"] = []
            session["seeded_puzzle_locked"] = True

            if session.get("seeded_puzzle_stopped_at") is None:
                session["seeded_puzzle_stopped_at"] = time.time()

            elapsed_time = self.calculateTime()
            self.displayResult(True, elapsed_time)

            leaderboard_rows = []
            if progression is not None:
                leaderboard_rows = progression.updatePlayerTime(seed, elapsed_time)

            return {
                "done": True,
                "locked": True,
                "elapsed_time": elapsed_time,
                "result": session.get("seeded_puzzle_result"),
                "leaderboard": leaderboard_rows,
            }

        self.displayResult(False)
        return {
            "done": False,
            "locked": False,
            "elapsed_time": session.get("seeded_puzzle_elapsed_time"),
            "result": session.get("seeded_puzzle_result"),
            "leaderboard": [],
        }
