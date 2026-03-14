from typing import Optional, Dict, Any
import json
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

    def _prefix_key(self, prefix: str, name: str) -> str:
        return f"{prefix}_{name}"

    def _get_seed_from_session(self, prefix: str) -> Optional[str]:
        return session.get(self._prefix_key(prefix, "seed"))

    def _board_key(self, prefix: str) -> str:
        return self._prefix_key(prefix, "board")

    def _invalid_key(self, prefix: str) -> str:
        return self._prefix_key(prefix, "invalid_positions")

    def _locked_key(self, prefix: str) -> str:
        return self._prefix_key(prefix, "locked")

    def _started_key(self, prefix: str) -> str:
        return self._prefix_key(prefix, "started_at")

    def _stopped_key(self, prefix: str) -> str:
        return self._prefix_key(prefix, "stopped_at")

    def _elapsed_key(self, prefix: str) -> str:
        return self._prefix_key(prefix, "elapsed_time")

    def _result_key(self, prefix: str) -> str:
        return self._prefix_key(prefix, "result")

    def _result_type_key(self, prefix: str) -> str:
        return self._prefix_key(prefix, "result_type")

    def resetState(self, prefix: str):
        session.pop(self._board_key(prefix), None)
        session.pop(self._invalid_key(prefix), None)
        session.pop(self._locked_key(prefix), None)
        session.pop(self._started_key(prefix), None)
        session.pop(self._stopped_key(prefix), None)
        session.pop(self._elapsed_key(prefix), None)
        session.pop(self._result_key(prefix), None)
        session.pop(self._result_type_key(prefix), None)

    def ensureState(self, prefix: str):
        if session.get(self._board_key(prefix)) is None:
            session[self._board_key(prefix)] = {}
        if session.get(self._invalid_key(prefix)) is None:
            session[self._invalid_key(prefix)] = []
        if session.get(self._locked_key(prefix)) is None:
            session[self._locked_key(prefix)] = False
        if session.get(self._started_key(prefix)) is None:
            session[self._started_key(prefix)] = time.time()

    def getBoardStateByPrefix(self, prefix: str) -> dict:
        self.ensureState(prefix)
        board = session.get(self._board_key(prefix), {})
        if not isinstance(board, dict):
            board = {}
            session[self._board_key(prefix)] = board
        return board

    def isLockedByPrefix(self, prefix: str) -> bool:
        self.ensureState(prefix)
        return session.get(self._locked_key(prefix), False) is True

    def getPlaySummaryByPrefix(self, prefix: str) -> Dict[str, Any]:
        self.ensureState(prefix)
        return {
            "board": dict(session.get(self._board_key(prefix), {})),
            "invalid_positions": list(session.get(self._invalid_key(prefix), [])),
            "locked": session.get(self._locked_key(prefix), False) is True,
            "result": session.get(self._result_key(prefix)),
            "result_type": session.get(self._result_type_key(prefix)),
            "elapsed_time": session.get(self._elapsed_key(prefix)),
        }

    def _loadRowFromPrefix(self, prefix: str) -> bool:
        if self._row:
            return True
        seed = self._get_seed_from_session(prefix)
        if not seed:
            return False
        return self.checkSeed(seed)

    def _isPlayablePosition(self, position: int) -> bool:
        if not self._row:
            return False
        try:
            pd = json.loads(self._row["puzzle_data"])
        except Exception:
            return False

        mask = pd.get("mask", "")
        if position < 0 or position >= len(mask):
            return False
        return mask[position] == "0"

    def _lockByPrefix(self, prefix: str):
        self.ensureState(prefix)
        session[self._locked_key(prefix)] = True

    def _stopTimerByPrefix(self, prefix: str):
        self.ensureState(prefix)
        if session.get(self._stopped_key(prefix)) is None:
            session[self._stopped_key(prefix)] = time.time()

    def _calculateTimeByPrefix(self, prefix: str):
        self.ensureState(prefix)
        start = session.get(self._started_key(prefix))
        stop = session.get(self._stopped_key(prefix))
        if start is None:
            start = time.time()
            session[self._started_key(prefix)] = start
        if stop is None:
            stop = time.time()
            session[self._stopped_key(prefix)] = stop
        elapsed = round(max(0.0, float(stop) - float(start)), 2)
        session[self._elapsed_key(prefix)] = elapsed
        return elapsed

    def resetPlayState(self):
        self.resetState("seeded_puzzle")

    def ensurePlayState(self):
        self.ensureState("seeded_puzzle")

    def getBoardState(self) -> dict:
        return self.getBoardStateByPrefix("seeded_puzzle")

    def isLocked(self) -> bool:
        return self.isLockedByPrefix("seeded_puzzle")

    def getPlaySummary(self) -> Dict[str, Any]:
        return self.getPlaySummaryByPrefix("seeded_puzzle")

    def fillCells(self, position, value):
        self.ensurePlayState()

        if self.isLocked():
            return {
                "ok": False,
                "error": "Puzzle is locked.",
                "invalid_positions": [],
                "locked": True,
            }

        if not self._loadRowFromPrefix("seeded_puzzle"):
            return {
                "ok": False,
                "error": "seed not found",
                "invalid_positions": [],
                "locked": False,
            }

        board = self.getBoardState()
        cell = Cell(position, board)

        if not self._isPlayablePosition(cell.position):
            invalid_positions = cell.highlightCell()
            session[self._invalid_key("seeded_puzzle")] = invalid_positions
            return {
                "ok": False,
                "position": cell.position,
                "value": board.get(str(cell.position), ""),
                "error": "Invalid input.",
                "invalid_positions": invalid_positions,
                "locked": False,
            }

        value_str = "" if value is None else str(value).strip()

        # Live validation only checks: empty OR one digit 1-9
        if value_str != "" and value_str not in {"1", "2", "3", "4", "5", "6", "7", "8", "9"}:
            invalid_positions = cell.highlightCell()
            session[self._invalid_key("seeded_puzzle")] = invalid_positions
            return {
                "ok": False,
                "position": cell.position,
                "value": value_str,
                "error": "Invalid input.",
                "invalid_positions": invalid_positions,
                "locked": False,
            }

        cell.setValue(value_str)
        session[self._board_key("seeded_puzzle")] = board
        session[self._invalid_key("seeded_puzzle")] = []

        if session.get(self._result_type_key("seeded_puzzle")) != "success":
            session.pop(self._result_key("seeded_puzzle"), None)
            session.pop(self._result_type_key("seeded_puzzle"), None)

        return {
            "ok": True,
            "position": cell.position,
            "value": value_str,
            "invalid_positions": [],
            "locked": False,
        }
    def lockPuzzle(self):
        self._lockByPrefix("seeded_puzzle")

    def stopTimer(self):
        self._stopTimerByPrefix("seeded_puzzle")

    def calculateTime(self):
        return self._calculateTimeByPrefix("seeded_puzzle")

    def displayResult(self, done: bool, elapsed_time: Optional[float] = None):
        if done:
            msg = "Puzzle completed!"
            if elapsed_time is not None:
                msg = f"Puzzle completed in {elapsed_time:.2f}s!"
            session[self._result_key("seeded_puzzle")] = msg
            session[self._result_type_key("seeded_puzzle")] = "success"
            return msg

        msg = "Puzzle is not complete yet."
        session[self._result_key("seeded_puzzle")] = msg
        session[self._result_type_key("seeded_puzzle")] = "error"
        return msg

    def checkPuzzle(self, progression=None):
        self.ensurePlayState()

        if not self._loadRowFromPrefix("seeded_puzzle"):
            return {"done": False, "error": "seed not found", "leaderboard": []}

        seed = self._row["seed"]
        board = self.getBoardState()
        done = self.db.isCompleted(seed, board)

        if done:
            session[self._invalid_key("seeded_puzzle")] = []
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
                "result": session.get(self._result_key("seeded_puzzle")),
                "leaderboard": leaderboard_rows,
            }

        self.displayResult(False)
        return {
            "done": False,
            "locked": False,
            "elapsed_time": session.get(self._elapsed_key("seeded_puzzle")),
            "result": session.get(self._result_key("seeded_puzzle")),
            "leaderboard": [],
        }

    def resetCampaignPlayState(self):
        self.resetState("campaign_puzzle")

    def ensureCampaignPlayState(self):
        self.ensureState("campaign_puzzle")

    def getCampaignBoardState(self) -> dict:
        return self.getBoardStateByPrefix("campaign_puzzle")

    def isCampaignLocked(self) -> bool:
        return self.isLockedByPrefix("campaign_puzzle")

    def getCampaignPlaySummary(self) -> Dict[str, Any]:
        return self.getPlaySummaryByPrefix("campaign_puzzle")

    def fillCampaignCells(self, position, value):
        self.ensureCampaignPlayState()

        if self.isCampaignLocked():
            return {
                "ok": False,
                "error": "Puzzle is locked.",
                "invalid_positions": [],
                "locked": True,
            }

        if not self._loadRowFromPrefix("campaign_puzzle"):
            return {
                "ok": False,
                "error": "level is not ready",
                "invalid_positions": [],
                "locked": False,
            }

        board = self.getCampaignBoardState()
        cell = Cell(position, board)

        if not self._isPlayablePosition(cell.position):
            invalid_positions = cell.highlightCell()
            session[self._invalid_key("campaign_puzzle")] = invalid_positions
            return {
                "ok": False,
                "position": cell.position,
                "value": board.get(str(cell.position), ""),
                "error": "Invalid input.",
                "invalid_positions": invalid_positions,
                "locked": False,
            }

        value_str = "" if value is None else str(value).strip()
        if value_str != "" and value_str not in {"1", "2", "3", "4", "5", "6", "7", "8", "9"}:
            invalid_positions = cell.highlightCell()
            session[self._invalid_key("campaign_puzzle")] = invalid_positions
            return {
                "ok": False,
                "position": cell.position,
                "value": value_str,
                "error": "Invalid input.",
                "invalid_positions": invalid_positions,
                "locked": False,
            }

        cell.setValue(value_str)
        session[self._board_key("campaign_puzzle")] = board
        session[self._invalid_key("campaign_puzzle")] = []
        if session.get(self._result_type_key("campaign_puzzle")) != "success":
            session.pop(self._result_key("campaign_puzzle"), None)
            session.pop(self._result_type_key("campaign_puzzle"), None)

        return {
            "ok": True,
            "position": cell.position,
            "value": value_str,
            "invalid_positions": [],
            "locked": False,
        }

    def displayCampaignResult(self, done: bool):
        if done:
            session[self._result_key("campaign_puzzle")] = "Solved"
            session[self._result_type_key("campaign_puzzle")] = "success"
            return "Solved"

        session[self._result_key("campaign_puzzle")] = "Not solved"
        session[self._result_type_key("campaign_puzzle")] = "error"
        return "Not solved"

    def checkCampaignPuzzle(self, campaign=None):
        self.ensureCampaignPlayState()

        if not self._loadRowFromPrefix("campaign_puzzle"):
            return {"done": False, "error": "level is not ready", "leaderboard": []}

        seed = self._row["seed"]
        board = self.getCampaignBoardState()
        done = self.db.isCompleted(seed, board)

        if done:
            session[self._invalid_key("campaign_puzzle")] = []
            self._lockByPrefix("campaign_puzzle")
            self._stopTimerByPrefix("campaign_puzzle")
            elapsed_time = self._calculateTimeByPrefix("campaign_puzzle")
            self.displayCampaignResult(True)

            campaign_info = {}
            if campaign is not None:
                campaign_info = campaign.completeCampaignPuzzle(seed, elapsed_time) or {}

            return {
                "done": True,
                "locked": True,
                "elapsed_time": elapsed_time,
                "result": session.get(self._result_key("campaign_puzzle")),
                "leaderboard": campaign_info.get("leaderboard_rows", []),
            }

        self.displayCampaignResult(False)
        return {
            "done": False,
            "locked": False,
            "elapsed_time": session.get(self._elapsed_key("campaign_puzzle")),
            "result": session.get(self._result_key("campaign_puzzle")),
            "leaderboard": [],
        }