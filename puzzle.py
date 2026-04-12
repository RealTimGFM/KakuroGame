from typing import Optional, Dict, Any
import json
import re
import time
from flask import session, has_request_context
from cell import Cell
from validator import Validator


class Puzzle:
    def __init__(self, db):
        self.db = db
        self._row = None
        self._seed_norm = None
        self.result = None
        self.result_type = None

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

        if has_request_context():
            self.result = session.get("seeded_puzzle_result")
            self.result_type = session.get("seeded_puzzle_result_type")
        else:
            self.result = None
            self.result_type = None

        return {
            "seed": self._row["seed"],
            "puzzle_data": self._row["puzzle_data"],
            "difficulty": self._row["difficulty"],
            "campaign_level": self._row["campaign_level"],
            "result": self.result,
            "result_type": self.result_type,
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
        self.result = None
        self.result_type = None

        payload = self.displayPuzzle()
        if payload is None:
            return None

        session["seeded_puzzle_seed"] = payload["seed"]
        self.startTimer()
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
            self.startTimer()

        self.result = session.get("seeded_puzzle_result")
        self.result_type = session.get("seeded_puzzle_result_type")

        return {
            "board": dict(board),
            "invalid_positions": list(invalid_positions),
            "locked": session.get("seeded_puzzle_locked", False) is True,
            "result": self.result,
            "result_type": self.result_type,
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
            self.startTimer()

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

    def fillGrid(self, digits: str):
        if not self._row:
            seed = session.get("seeded_puzzle_seed")
            if not seed or not self.checkSeed(seed):
                return None

        try:
            puzzle_obj = json.loads(self._row["puzzle_data"])
            width = int(puzzle_obj["w"])
            height = int(puzzle_obj["h"])
            mask = str(puzzle_obj["mask"])
        except Exception:
            return None

        board = {}
        for index in range(width * height):
            if index >= len(mask) or mask[index] != "0":
                continue

            token = digits[index] if index < len(digits) else "."
            board[str(index)] = "" if token == "." else str(token)

        session["seeded_puzzle_board"] = board
        session["seeded_puzzle_invalid_positions"] = []
        return board

    def lockGrid(self):
        if session.get("seeded_puzzle_locked") is None:
            session["seeded_puzzle_locked"] = False
        session["seeded_puzzle_locked"] = True

    def startTimer(self):
        if session.get("seeded_puzzle_started_at") is None:
            session["seeded_puzzle_started_at"] = time.time()
        session.pop("seeded_puzzle_stopped_at", None)
        session.pop("seeded_puzzle_elapsed_time", None)

    def stopTimer(self):
        if session.get("seeded_puzzle_started_at") is None:
            self.startTimer()

        if session.get("seeded_puzzle_stopped_at") is None:
            session["seeded_puzzle_stopped_at"] = time.time()

    def calculateTime(self):
        if session.get("seeded_puzzle_started_at") is None:
            self.startTimer()

        start = session.get("seeded_puzzle_started_at")
        stop = session.get("seeded_puzzle_stopped_at")

        if stop is None:
            stop = time.time()
            session["seeded_puzzle_stopped_at"] = stop

        elapsed = round(max(0.0, float(stop) - float(start)), 2)
        session["seeded_puzzle_elapsed_time"] = elapsed
        return elapsed

    def setResult(self, result: str):
        normalized = str(result or "").strip().lower()

        if normalized == "solved":
            session["seeded_puzzle_result"] = "Solved"
            session["seeded_puzzle_result_type"] = "success"
            self.result = session["seeded_puzzle_result"]
            self.result_type = session["seeded_puzzle_result_type"]
            return session["seeded_puzzle_result"]

        if normalized == "not solved":
            session["seeded_puzzle_result"] = "Not Solved"
            session["seeded_puzzle_result_type"] = "error"
            self.result = session["seeded_puzzle_result"]
            self.result_type = session["seeded_puzzle_result_type"]
            return session["seeded_puzzle_result"]

        session["seeded_puzzle_result"] = str(result)
        session["seeded_puzzle_result_type"] = "error"
        self.result = session["seeded_puzzle_result"]
        self.result_type = session["seeded_puzzle_result_type"]
        return session["seeded_puzzle_result"]

    def displayResult(self, done: bool, elapsed_time: Optional[float] = None):
        if done:
            self.setResult("Solved")
            if elapsed_time is not None:
                session["seeded_puzzle_result"] = (
                    f'{session["seeded_puzzle_result"]} in {elapsed_time:.2f}s'
                )
                self.result = session["seeded_puzzle_result"]
                self.result_type = session["seeded_puzzle_result_type"]
            return session["seeded_puzzle_result"]

        return self.setResult("Not Solved")

    def showSolution(self, progression=None):
        if self.isLocked():
            return {
                "ok": False,
                "error": "Puzzle is locked.",
                "locked": True,
            }

        if not self._row:
            seed = session.get("seeded_puzzle_seed")
            if not seed or not self.checkSeed(seed):
                return {
                    "ok": False,
                    "error": "seed not found",
                    "locked": False,
                }

        solution_row = self.db.get_puzzle_solution(self._row["seed"])
        digits = None
        if solution_row:
            try:
                solution_obj = json.loads(solution_row["solution_data"])
                raw_digits = solution_obj.get("digits", "")
                if isinstance(raw_digits, str):
                    digits = raw_digits
            except Exception:
                digits = None

        if not digits:
            session["seeded_puzzle_result"] = "Solution unavailable."
            session["seeded_puzzle_result_type"] = "error"
            self.result = session["seeded_puzzle_result"]
            self.result_type = session["seeded_puzzle_result_type"]
            return {
                "ok": False,
                "error": "solution unavailable",
                "locked": False,
            }

        board = self.fillGrid(digits)
        if board is None:
            session["seeded_puzzle_result"] = "Solution unavailable."
            session["seeded_puzzle_result_type"] = "error"
            self.result = session["seeded_puzzle_result"]
            self.result_type = session["seeded_puzzle_result_type"]
            return {
                "ok": False,
                "error": "solution unavailable",
                "locked": False,
            }

        self.stopTimer()
        elapsed_time = self.calculateTime()
        self.lockGrid()
        session["seeded_puzzle_result"] = f"Solution shown in {elapsed_time:.2f}s"
        session["seeded_puzzle_result_type"] = "error"
        self.result = session["seeded_puzzle_result"]
        self.result_type = session["seeded_puzzle_result_type"]

        seed = self._row["seed"] if self._row else session.get("seeded_puzzle_seed")

        if progression is not None:
            if session.get("play_context") == "campaign":
                progression.flagIneligible()
            if seed:
                uid = session.get("user_id")
                if isinstance(uid, int):
                    self.db.ensure_progression_row(uid)
                    self.db.mark_user_played_seed(uid, seed)
                    con = self.db.get_connection()
                    cur = con.cursor()
                    cur.execute(
                        """
                        UPDATE user_puzzles
                        SET completed_at = CURRENT_TIMESTAMP,
                            last_elapsed_time = ?,
                            solution_shown = 1
                        WHERE user_id = ? AND seed = ?
                    """,
                        (float(elapsed_time), uid, seed),
                    )
                    con.commit()
                    con.close()

        return {
            "ok": True,
            "board": dict(board),
            "invalid_positions": [],
            "locked": True,
            "elapsed_time": elapsed_time,
            "result": session.get("seeded_puzzle_result"),
            "ineligible": session.get("campaign_ineligible", False) is True,
        }

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
            self.startTimer()

        if session.get("seeded_puzzle_locked", False) is True:
            return {
                "done": False,
                "error": "Puzzle is locked.",
                "locked": True,
                "elapsed_time": session.get("seeded_puzzle_elapsed_time"),
                "result": session.get("seeded_puzzle_result"),
                "leaderboard": [],
            }

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
            self.result = session["seeded_puzzle_result"]
            self.result_type = session["seeded_puzzle_result_type"]

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
    def restartPuzzle(self):
        if not self._row:
            seed = session.get("seeded_puzzle_seed")
            if not seed or not self.checkSeed(seed):
                return {
                    "ok": False,
                    "error": "seed not found",
                }

        current_seed = self._row["seed"]
        next_seed = current_seed

        difficulty = self._row["difficulty"]
        campaign_level = self._row["campaign_level"]

        if difficulty is not None and campaign_level is not None:
            rows = self.db.getPuzzleSkill(difficulty, int(campaign_level)) or []

            for row in rows:
                if row["seed"] != current_seed:
                    next_seed = row["seed"]
                    break

        if not self.checkSeed(next_seed):
            return {
                "ok": False,
                "error": "restart failed",
            }

        session.pop("seeded_puzzle_board", None)
        session.pop("seeded_puzzle_invalid_positions", None)
        session.pop("seeded_puzzle_locked", None)
        session.pop("seeded_puzzle_started_at", None)
        session.pop("seeded_puzzle_stopped_at", None)
        session.pop("seeded_puzzle_elapsed_time", None)
        session.pop("seeded_puzzle_result", None)
        session.pop("seeded_puzzle_result_type", None)
        session.pop("post_solve_signup_seed", None)

        self.result = None
        self.result_type = None

        payload = self.displayPuzzle()
        if payload is None:
            return {
                "ok": False,
                "error": "restart failed",
            }

        session["seeded_puzzle_seed"] = payload["seed"]

        if session.get("play_context") == "campaign":
            session["campaign_current_seed"] = payload["seed"]

        self.startTimer()

        return {
            "ok": True,
            "seed": payload["seed"],
            "changed_puzzle": payload["seed"] != current_seed,
            "puzzle": payload,
        }
