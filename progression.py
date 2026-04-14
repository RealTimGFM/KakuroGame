from flask import flash, session
from typing import Optional, Dict, Any
from puzzle import Puzzle
from leaderboard import Leaderboard
from campaign import Campaign


class Progression:
    def __init__(self, db):
        self.db = db

    def setMode(self, mode: str):
        m = (mode or "").strip()

        if m not in ("Campaign", "Single Puzzle"):
            flash("Invalid mode.", "error")
            return

        uid = session.get("user_id")
        if isinstance(uid, int):
            self.db.ensure_progression_row(uid)
            self.db.set_mode(uid, m)
        else:
            session["guest_mode"] = m

    def setDifficulty(self, difficulty: str):
        campaign = Campaign(self.db)
        diff = campaign.normalizeDifficulty(difficulty)

        uid = session.get("user_id")
        if isinstance(uid, int):
            self.db.ensure_progression_row(uid)
            self.db.set_difficulty(uid, diff)
        else:
            session["guest_difficulty"] = diff

    def setLevel(self, level: int):
        try:
            lvl = int(level)
        except Exception:
            flash("Invalid level.", "error")
            return

        if lvl < 1:
            flash("Invalid level.", "error")
            return

        uid = session.get("user_id")
        if isinstance(uid, int):
            self.db.ensure_progression_row(uid)
            self.db.set_campaign_level(uid, lvl)
        else:
            session["guest_level"] = lvl

    def loadProgression(self, user_id: int):
        self.db.ensure_progression_row(user_id)

        guest_mode = session.get("guest_mode")
        guest_difficulty = session.get("guest_difficulty")
        guest_level = session.get("guest_level")

        if guest_mode in ("Campaign", "Single Puzzle"):
            self.db.set_mode(user_id, guest_mode)

        if guest_difficulty:
            self.db.set_difficulty(
                user_id,
                Campaign(self.db).normalizeDifficulty(guest_difficulty),
            )

        if isinstance(guest_level, int) and guest_level >= 1:
            self.db.set_campaign_level(user_id, guest_level)

        guest_games = session.get("guest_games", [])
        if isinstance(guest_games, list):
            for seed in guest_games:
                if isinstance(seed, str) and self.db.get_puzzle_by_seed(seed):
                    self.db.mark_user_played_seed(user_id, seed)

        session.pop("guest_games", None)
        session.pop("guest_mode", None)
        session.pop("guest_difficulty", None)
        session.pop("guest_level", None)

    def playCampaign(self) -> Optional[Dict[str, Any]]:
        campaign = Campaign(self.db)
        progress = campaign.checkProgression()

        campaign.startRun()
        self.setMode("Campaign")
        campaign.setGame(progress["difficulty"], progress["level"])

        return campaign.loadLevelPuzzle()

    def updateLastUnlockedLevel(self):
        campaign = Campaign(self.db)

        current_difficulty = campaign.normalizeDifficulty(
            session.get("campaign_current_difficulty", "Learner")
        )
        current_level = int(session.get("campaign_current_level", 1) or 1)

        next_progress = campaign.getNextProgress(current_difficulty, current_level)
        if next_progress is None:
            unlocked_difficulty = current_difficulty
            unlocked_level = current_level
        else:
            unlocked_difficulty = next_progress["difficulty"]
            unlocked_level = next_progress["level"]

        uid = session.get("user_id")
        if isinstance(uid, int):
            self.db.ensure_progression_row(uid)
            row = self.db.get_progression(uid)

            stored_difficulty = campaign.normalizeDifficulty(
                row["difficulty"] if row and row["difficulty"] else "Learner"
            )
            stored_level = int(
                row["campaign_level"]
                if row and row["campaign_level"] is not None
                else 1
            )

            unlocked_rank = (
                campaign.DIFFICULTIES.index(unlocked_difficulty) + 1,
                int(unlocked_level),
            )
            stored_rank = (
                campaign.DIFFICULTIES.index(stored_difficulty) + 1,
                int(stored_level),
            )
            if unlocked_rank > stored_rank:
                self.db.set_difficulty(uid, unlocked_difficulty)
                self.db.set_campaign_level(uid, unlocked_level)
        else:
            stored_difficulty = campaign.normalizeDifficulty(
                session.get("guest_difficulty", "Learner")
            )
            stored_level = int(session.get("guest_level", 1) or 1)

            unlocked_rank = (
                campaign.DIFFICULTIES.index(unlocked_difficulty) + 1,
                int(unlocked_level),
            )
            stored_rank = (
                campaign.DIFFICULTIES.index(stored_difficulty) + 1,
                int(stored_level),
            )
            if unlocked_rank > stored_rank:
                session["guest_difficulty"] = unlocked_difficulty
                session["guest_level"] = unlocked_level

        return {
            "difficulty": unlocked_difficulty,
            "level": unlocked_level,
        }

    def advanceCampaign(self):
        if session.get("play_context") != "campaign":
            return {"finished": False}

        campaign = Campaign(self.db)
        run_ineligible = session.get("campaign_ineligible", False) is True
        current_difficulty = campaign.normalizeDifficulty(
            session.get("campaign_current_difficulty", "Learner")
        )
        current_level = int(session.get("campaign_current_level", 1) or 1)
        current_display = (
            f"{campaign.DIFFICULTIES.index(current_difficulty) + 1}-{int(current_level)}"
        )

        completed = list(session.get("campaign_completed_levels", []))
        marker = f"{current_difficulty}:{current_level}"
        if marker not in completed:
            completed.append(marker)
            session["campaign_completed_levels"] = completed

        self.updateLastUnlockedLevel()

        if campaign.isLastRound(current_difficulty, current_level):
            total_time = campaign.calculateCampaignTime()
            rows = []

            uid = session.get("user_id")
            if isinstance(uid, int) and not run_ineligible:
                rows = Leaderboard(self.db).setCampaignLeaderboard(uid, total_time)

            if run_ineligible:
                campaign.displayMsg(
                    f"Campaign completed in {total_time:.2f}s, but this run is ineligible.",
                    "error",
                )
            else:
                campaign.displayMsg(f"Campaign completed in {total_time:.2f}s!", "success")

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

            if isinstance(uid, int):
                self.db.clear_campaign_run(uid)

            return {
                "finished": True,
                "elapsed_time": total_time,
                "leaderboard": rows,
            }

        payload = campaign.loadNextLevel()
        if payload is None:
            campaign.displayMsg("No next campaign puzzle was found.", "error")

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

            uid = session.get("user_id")
            if isinstance(uid, int):
                self.db.clear_campaign_run(uid)

            return {
                "finished": True,
                "elapsed_time": None,
                "leaderboard": [],
            }

        next_difficulty = campaign.normalizeDifficulty(
            session.get("campaign_current_difficulty", "Learner")
        )
        next_level = int(session.get("campaign_current_level", 1) or 1)
        next_display = (
            f"{campaign.DIFFICULTIES.index(next_difficulty) + 1}-{int(next_level)}"
        )

        campaign.displayMsg(
            f"Level {current_display} completed. Continue to level {next_display}.",
            "success",
        )
        return {
            "finished": False,
            "next_seed": payload["seed"],
        }

    def enterPuzzleSeed(self, seed: str) -> Optional[Dict[str, Any]]:
        p = Puzzle(self.db)

        if not p.checkSeed(seed):
            flash("Seed not found (or invalid).", "error")
            return None

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

        uid = session.get("user_id")
        if isinstance(uid, int):
            self.db.clear_campaign_run(uid)

        self.setMode("Single Puzzle")

        payload = p.displayPuzzle()
        if payload is None:
            flash("Puzzle load failed.", "error")
            return None

        seed_norm = payload["seed"]

        uid = session.get("user_id")
        if isinstance(uid, int):
            self.db.mark_user_played_seed(uid, seed_norm)
        else:
            games = session.get("guest_games", [])
            if not isinstance(games, list):
                games = []
            if seed_norm not in games:
                games.append(seed_norm)
            session["guest_games"] = games

        return payload

    def enterSeededMode(self, seed: str) -> Optional[Dict[str, Any]]:
        payload = self.enterPuzzleSeed(seed)
        if payload is None:
            return None

        session.pop("seeded_puzzle_board", None)
        session.pop("seeded_puzzle_invalid_positions", None)
        session.pop("seeded_puzzle_locked", None)
        session.pop("seeded_puzzle_started_at", None)
        session.pop("seeded_puzzle_stopped_at", None)
        session.pop("seeded_puzzle_elapsed_time", None)
        session.pop("seeded_puzzle_result", None)
        session.pop("seeded_puzzle_result_type", None)

        session["seeded_puzzle_seed"] = payload["seed"]
        session["play_context"] = "single_puzzle"
        return payload

    def exitSeededMode(self):
        session.pop("seeded_puzzle_seed", None)
        session.pop("seeded_puzzle_board", None)
        session.pop("seeded_puzzle_invalid_positions", None)
        session.pop("seeded_puzzle_locked", None)
        session.pop("seeded_puzzle_started_at", None)
        session.pop("seeded_puzzle_stopped_at", None)
        session.pop("seeded_puzzle_elapsed_time", None)
        session.pop("seeded_puzzle_result", None)
        session.pop("seeded_puzzle_result_type", None)

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

        self.setMode("Campaign")

    def completeSeededPuzzle(self):
        session.pop("seeded_puzzle_seed", None)
        session.pop("seeded_puzzle_board", None)
        session.pop("seeded_puzzle_invalid_positions", None)
        session.pop("seeded_puzzle_locked", None)
        session.pop("seeded_puzzle_started_at", None)
        session.pop("seeded_puzzle_stopped_at", None)
        session.pop("seeded_puzzle_elapsed_time", None)
        session.pop("seeded_puzzle_result", None)
        session.pop("seeded_puzzle_result_type", None)

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

        uid = session.get("user_id")
        if isinstance(uid, int):
            self.db.ensure_progression_row(uid)
            self.db.set_mode(uid, "Campaign")
            self.db.clear_campaign_run(uid)
        else:
            session["guest_mode"] = "Campaign"
            session["guest_difficulty"] = "Learner"
            session["guest_level"] = 1

    def flagIneligible(self):
        if session.get("play_context") != "campaign":
            return False

        session["campaign_ineligible"] = True

        uid = session.get("user_id")
        if isinstance(uid, int):
            self.db.ensure_progression_row(uid)
            self.db.save_campaign_run(
                uid,
                active=True,
                difficulty=session.get("campaign_current_difficulty"),
                level=int(session.get("campaign_current_level", 1) or 1),
                seed=session.get("campaign_current_seed"),
                started_at=float(session.get("campaign_started_at"))
                if session.get("campaign_started_at") is not None
                else None,
                ineligible=1,
            )

        return True

    def updatePlayerTime(
        self, seed: str, elapsed_time: float, user_id: Optional[int] = None
    ):
        uid = user_id if isinstance(user_id, int) else session.get("user_id")

        if not isinstance(uid, int):
            return []

        self.db.ensure_progression_row(uid)
        self.db.update(uid, seed, elapsed_time)

        lb = Leaderboard(self.db)
        return lb.setPuzzleLeaderboard(uid, seed, elapsed_time)
