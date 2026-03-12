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

    def _get_seed_from_session(self) -> Optional[str]:
        return session.get("seeded_puzzle_seed")

    def _board_key(self) -> str:
        return "seeded_puzzle_board"

    def _invalid_key(self) -> str:
        return "seeded_puzzle_invalid_positions"

    def _locked_key(self) -> str:
        return "seeded_puzzle_locked"

    def _started_key(self) -> str:
        return "seeded_puzzle_started_at"

    def _stopped_key(self) -> str:
        return "seeded_puzzle_stopped_at"

    def _elapsed_key(self) -> str:
        return "seeded_puzzle_elapsed_time"

    def _result_key(self) -> str:
        return "seeded_puzzle_result"

    def _result_type_key(self) -> str:
        return "seeded_puzzle_result_type"

    def resetPlayState(self):
        session.pop(self._board_key(), None)
        session.pop(self._invalid_key(), None)
        session.pop(self._locked_key(), None)
        session.pop(self._started_key(), None)
        session.pop(self._stopped_key(), None)
        session.pop(self._elapsed_key(), None)
        session.pop(self._result_key(), None)
        session.pop(self._result_type_key(), None)

    def ensurePlayState(self):
        if session.get(self._board_key()) is None:
            session[self._board_key()] = {}
        if session.get(self._invalid_key()) is None:
            session[self._invalid_key()] = []
        if session.get(self._locked_key()) is None:
            session[self._locked_key()] = False
        if session.get(self._started_key()) is None:
            session[self._started_key()] = time.time()

    def getBoardState(self) -> dict:
        self.ensurePlayState()
        board = session.get(self._board_key(), {})
        if not isinstance(board, dict):
            board = {}
            session[self._board_key()] = board
        return board

    def isLocked(self) -> bool:
        self.ensurePlayState()
        return session.get(self._locked_key(), False) is True

    def getPlaySummary(self) -> Dict[str, Any]:
        self.ensurePlayState()
        return {
            "board": dict(session.get(self._board_key(), {})),
            "invalid_positions": list(session.get(self._invalid_key(), [])),
            "locked": session.get(self._locked_key(), False) is True,
            "result": session.get(self._result_key()),
            "result_type": session.get(self._result_type_key()),
            "elapsed_time": session.get(self._elapsed_key()),
        }

    def fillCells(self, position, value):
        self.ensurePlayState()

        if self.isLocked():
            return {
                "ok": False,
                "error": "Puzzle is locked.",
                "invalid_positions": [],
                "locked": True,
            }

        if not self._row:
            seed = self._get_seed_from_session()
            if not seed or not self.checkSeed(seed):
                return {
                    "ok": False,
                    "error": "seed not found",
                    "invalid_positions": [],
                    "locked": False,
                }

        board = self.getBoardState()
        cell = Cell(position, board)
        validator = Validator.create(self._row["puzzle_data"], cell.position, value, board)
        valid = validator.checkInput()

        if valid:
            cell.setValue(value)
            session[self._board_key()] = board
            session[self._invalid_key()] = []
            if session.get(self._result_type_key()) != "success":
                session.pop(self._result_key(), None)
                session.pop(self._result_type_key(), None)
            return {
                "ok": True,
                "position": cell.position,
                "value": "" if value is None else str(value).strip(),
                "invalid_positions": [],
                "locked": False,
            }

        invalid_positions = cell.highlightCell()
        session[self._invalid_key()] = invalid_positions
        return {
            "ok": False,
            "position": cell.position,
            "value": board.get(str(cell.position), ""),
            "error": "Invalid input.",
            "invalid_positions": invalid_positions,
            "locked": False,
        }

    def lockPuzzle(self):
        self.ensurePlayState()
        session[self._locked_key()] = True

    def stopTimer(self):
        self.ensurePlayState()
        if session.get(self._stopped_key()) is None:
            session[self._stopped_key()] = time.time()

    def calculateTime(self):
        self.ensurePlayState()
        start = session.get(self._started_key())
        stop = session.get(self._stopped_key())
        if start is None:
            start = time.time()
            session[self._started_key()] = start
        if stop is None:
            stop = time.time()
            session[self._stopped_key()] = stop
        elapsed = round(max(0.0, float(stop) - float(start)), 2)
        session[self._elapsed_key()] = elapsed
        return elapsed

    def displayResult(self, done: bool, elapsed_time: Optional[float] = None):
        if done:
            msg = "Puzzle completed!"
            if elapsed_time is not None:
                msg = f"Puzzle completed in {elapsed_time:.2f}s!"
            session[self._result_key()] = msg
            session[self._result_type_key()] = "success"
            return msg

        msg = "Puzzle is not complete yet."
        session[self._result_key()] = msg
        session[self._result_type_key()] = "error"
        return msg

    def checkPuzzle(self, progression=None):
        self.ensurePlayState()

        if not self._row:
            seed = self._get_seed_from_session()
            if not seed or not self.checkSeed(seed):
                return {"done": False, "error": "seed not found", "leaderboard": []}

        seed = self._row["seed"]
        board = self.getBoardState()
        done = self.db.isCompleted(seed, board)

        if done:
            session[self._invalid_key()] = []
            self.lockPuzzle()
            self.stopTimer()
            elapsed_time = self.calculateTime()
            self.displayResult(True, elapsed_time)

            leaderboard_rows = []
            if progression is not None:
                leaderboard_rows = progression.updatePlayerTime(seed, elapsed_time)

            return {
                "done": True,
                "locked": True,
                "elapsed_time": elapsed_time,
                "result": session.get(self._result_key()),
                "leaderboard": leaderboard_rows,
            }

        self.displayResult(False)
        return {
            "done": False,
            "locked": False,
            "elapsed_time": session.get(self._elapsed_key()),
            "result": session.get(self._result_key()),
            "leaderboard": [],
        }