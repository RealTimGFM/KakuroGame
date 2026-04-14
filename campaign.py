import time
import random
from flask import flash, session
from puzzle import Puzzle


class Campaign:
    DIFFICULTIES = ["Learner", "Intermediate", "Master"]

    def __init__(self, db):
        self.db = db

    def normalizeDifficulty(self, difficulty: str) -> str:
        raw = str(difficulty or "").strip().lower()
        for item in self.DIFFICULTIES:
            if item.lower() == raw:
                return item
        return "Learner"

    def getNextProgress(self, difficulty: str, level: int):
        diff = self.normalizeDifficulty(difficulty)
        lvl = max(1, int(level))
        max_level = self.db.get_max_campaign_level_for_difficulty(diff)

        if lvl < max_level:
            return {
                "difficulty": diff,
                "level": lvl + 1,
            }

        idx = self.DIFFICULTIES.index(diff)
        if idx + 1 >= len(self.DIFFICULTIES):
            return None

        return {
            "difficulty": self.DIFFICULTIES[idx + 1],
            "level": 1,
        }

    def isLastRound(self, difficulty: str, level: int) -> bool:
        diff = self.normalizeDifficulty(difficulty)
        lvl = max(1, int(level))
        max_level = self.db.get_max_campaign_level_for_difficulty(diff)
        return diff == self.DIFFICULTIES[-1] and lvl >= max_level

    def checkProgression(self):
        uid = session.get("user_id")

        if isinstance(uid, int):
            self.db.ensure_progression_row(uid)
            row = self.db.get_progression(uid)

            difficulty = self.normalizeDifficulty(
                row["difficulty"] if row and row["difficulty"] else "Learner"
            )
            level = int(
                row["campaign_level"]
                if row and row["campaign_level"] is not None
                else 1
            )
        else:
            difficulty = self.normalizeDifficulty(
                session.get("guest_difficulty", "Learner")
            )
            level = int(session.get("guest_level", 1) or 1)

        return {
            "difficulty": difficulty,
            "level": max(1, level),
        }

    def setGame(self, difficulty: str, level: int):
        diff = self.normalizeDifficulty(difficulty)
        lvl = max(1, int(level))

        session["campaign_current_difficulty"] = diff
        session["campaign_current_level"] = lvl

        uid = session.get("user_id")
        if isinstance(uid, int):
            started_at = session.get("campaign_started_at")
            self.db.save_campaign_run(
                uid,
                active=True,
                difficulty=diff,
                level=lvl,
                seed=None,
                started_at=float(started_at) if started_at is not None else None,
                ineligible=1 if session.get("campaign_ineligible", False) is True else 0,
            )

        return {
            "difficulty": diff,
            "level": lvl,
        }

    def startRun(self):
        for key in (
            "campaign_active",
            "campaign_started_at",
            "campaign_elapsed_time",
            "campaign_ineligible",
            "campaign_current_difficulty",
            "campaign_current_level",
            "campaign_current_seed",
            "campaign_completed_levels",
            "campaign_seen_seeds",
            "campaign_last_message",
            "play_context",
        ):
            session.pop(key, None)

        session["campaign_active"] = True
        session["play_context"] = "campaign"
        session["campaign_started_at"] = time.time()
        session["campaign_ineligible"] = False
        session["campaign_completed_levels"] = []
        session["campaign_seen_seeds"] = []

        uid = session.get("user_id")
        if isinstance(uid, int):
            self.db.save_campaign_run(
                uid,
                active=True,
                difficulty=None,
                level=None,
                seed=None,
                started_at=float(session["campaign_started_at"]),
                ineligible=0,
            )

    def loadLevelPuzzle(self):
        difficulty = self.normalizeDifficulty(
            session.get("campaign_current_difficulty", "Learner")
        )
        level = int(session.get("campaign_current_level", 1) or 1)
        seen = list(session.get("campaign_seen_seeds", []))

        seed = self.getRandomPuzzle(difficulty, level, excluded_seeds=seen)
        if not seed:
            return None

        puzzle = Puzzle(self.db)
        payload = puzzle.loadPuzzle(seed)
        if payload is None:
            return None

        if payload["seed"] not in seen:
            seen.append(payload["seed"])
            session["campaign_seen_seeds"] = seen

        session["campaign_current_seed"] = payload["seed"]

        uid = session.get("user_id")
        if isinstance(uid, int):
            started_at = session.get("campaign_started_at")
            self.db.save_campaign_run(
                uid,
                active=True,
                difficulty=difficulty,
                level=level,
                seed=payload["seed"],
                started_at=float(started_at) if started_at is not None else None,
                ineligible=1 if session.get("campaign_ineligible", False) is True else 0,
            )
        return payload

    def getRandomPuzzle(self, difficulty: str, level: int, excluded_seeds=None):
        rows = list(self.db.getPuzzleSkill(difficulty, int(level)) or [])
        if not rows:
            return None

        excluded = set(excluded_seeds or [])
        filtered = [row for row in rows if row["seed"] not in excluded]
        choices = filtered if filtered else rows
        picked = random.choice(choices)
        return picked["seed"]

    def loadNextLevel(self):
        current_difficulty = self.normalizeDifficulty(
            session.get("campaign_current_difficulty", "Learner")
        )
        current_level = int(session.get("campaign_current_level", 1) or 1)

        next_progress = self.getNextProgress(current_difficulty, current_level)
        if next_progress is None:
            return None

        self.setGame(next_progress["difficulty"], next_progress["level"])
        return self.loadLevelPuzzle()

    def calculateCampaignTime(self):
        started = session.get("campaign_started_at")

        if started is None:
            started = time.time()
            session["campaign_started_at"] = started

        elapsed = round(max(0.0, time.time() - float(started)), 2)
        session["campaign_elapsed_time"] = elapsed
        return elapsed

    def displayMsg(self, msg: str, category: str = "success"):
        flash(msg, category)
        session["campaign_last_message"] = msg
