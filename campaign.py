from flask import session
from typing import Optional, Dict, Any
from puzzle import Puzzle


class Campaign:
    def __init__(self, db, progression):
        self.db = db
        self.progression = progression

    def _clearCampaignPlayState(self):
        p = Puzzle(self.db)
        p.resetCampaignPlayState()

    def _getOrCreateCampaignRun(self, current_level: int):
        uid = session.get("user_id")

        if isinstance(uid, int):
            self.db.ensure_progression_row(uid)
            run = self.db.get_latest_open_campaign_run(uid)
            if run is None:
                run_id = self.db.create_campaign_run(
                    user_id=uid,
                    is_guest=False,
                    current_level=current_level,
                )
            else:
                run_id = run["id"]
                self.db.set_campaign_run_level(run_id, current_level)

            session["campaign_run_id"] = run_id
            return run_id

        run_id = session.get("campaign_run_id")
        if isinstance(run_id, int):
            run = self.db.get_campaign_run(run_id)
            if run is not None and run["completed_at"] is None:
                self.db.set_campaign_run_level(run_id, current_level)
                return run_id

        run_id = self.db.create_campaign_run(
            user_id=None,
            is_guest=True,
            current_level=current_level,
        )
        session["campaign_run_id"] = run_id
        return run_id

    def startCampaign(self) -> Optional[Dict[str, Any]]:
        self.progression.setMode("Campaign")
        level = self.progression.getOfficialCampaignLevel()
        return self.startCampaignLevel(level)

    def startCampaignLevel(self, level: int) -> Optional[Dict[str, Any]]:
        try:
            lvl = int(level)
        except Exception:
            self.progression.displayError("Invalid level.")
            return None

        if lvl < 1 or lvl > 15:
            self.progression.displayError("Invalid level.")
            return None

        run_id = self._getOrCreateCampaignRun(lvl)
        last_seed = self.db.get_last_played_seed_for_run_level(run_id, lvl)
        puzzle_row = self.db.get_random_puzzle_for_campaign_level(
            lvl,
            exclude_seed=last_seed,
        )

        if puzzle_row is None:
            self.progression.displayError("Level is not ready.")
            return None

        self._clearCampaignPlayState()
        session["campaign_puzzle_seed"] = puzzle_row["seed"]
        session["campaign_current_level"] = lvl
        session["campaign_guest_prompt"] = False
        session.pop("campaign_next_level", None)
        session.pop("campaign_completed", None)
        session.pop("campaign_total_elapsed_time", None)

        self.db.set_campaign_run_level(run_id, lvl)
        self.db.create_campaign_level_run(run_id, lvl, puzzle_row["seed"])

        return {
            "seed": puzzle_row["seed"],
            "official_level": lvl,
        }

    def restartCampaignLevel(self) -> Optional[Dict[str, Any]]:
        level = session.get("campaign_current_level", self.progression.getOfficialCampaignLevel())
        run_id = session.get("campaign_run_id")
        seed = session.get("campaign_puzzle_seed")

        if isinstance(run_id, int) and isinstance(seed, str):
            self.db.close_active_campaign_level_run(
                run_id,
                seed,
                "Restarted",
                is_solved=0,
                elapsed_time=None,
            )

        return self.startCampaignLevel(level)

    def leaveCampaign(self):
        run_id = session.get("campaign_run_id")
        seed = session.get("campaign_puzzle_seed")
        locked = session.get("campaign_puzzle_locked", False) is True

        if isinstance(run_id, int) and isinstance(seed, str) and not locked:
            self.db.close_active_campaign_level_run(
                run_id,
                seed,
                "Left",
                is_solved=0,
                elapsed_time=None,
            )

        self._clearCampaignPlayState()
        session.pop("campaign_puzzle_seed", None)
        session.pop("campaign_current_level", None)
        session.pop("campaign_next_level", None)
        session.pop("campaign_guest_prompt", None)
        session.pop("campaign_completed", None)
        session.pop("campaign_total_elapsed_time", None)

        self.progression.returnCampaign()

    def completeCampaignPuzzle(self, seed: str, elapsed_time: float):
        run_id = session.get("campaign_run_id")
        current_level = int(
            session.get("campaign_current_level", self.progression.getOfficialCampaignLevel())
        )

        if isinstance(run_id, int):
            self.db.complete_campaign_level_run(
                run_id,
                seed,
                elapsed_time,
                "Solved",
                is_solved=1,
            )

        uid = session.get("user_id")
        leaderboard_rows = self.db.get_leaderboard_by_seed(seed)

        if isinstance(uid, int):
            leaderboard_rows = self.progression.updatePlayerTime(
                seed,
                elapsed_time,
                user_id=uid,
            )
        else:
            session["campaign_guest_prompt"] = True

        next_level = current_level + 1 if current_level < 15 else None
        if next_level is not None:
            self.progression.setLevel(next_level)
            session["campaign_next_level"] = next_level
            if isinstance(run_id, int):
                self.db.set_campaign_run_level(run_id, next_level)
        else:
            session.pop("campaign_next_level", None)

        campaign_completed = current_level == 15
        campaign_leaderboard_rows = []

        if campaign_completed:
            total_elapsed_time = elapsed_time
            if isinstance(run_id, int):
                total_elapsed_time = self.db.sum_campaign_elapsed_time(run_id)
                self.db.complete_campaign_run(run_id, total_elapsed_time)

            session["campaign_completed"] = True
            session["campaign_total_elapsed_time"] = total_elapsed_time

            if isinstance(uid, int):
                campaign_leaderboard_rows = self.db.upsert_campaign_leaderboard(
                    uid,
                    total_elapsed_time,
                )
            else:
                session["campaign_guest_prompt"] = True

        return {
            "leaderboard_rows": leaderboard_rows,
            "next_level": next_level,
            "campaign_completed": campaign_completed,
            "campaign_leaderboard_rows": campaign_leaderboard_rows,
        }

    def advanceCampaignAfterSolve(self) -> Optional[Dict[str, Any]]:
        next_level = session.get("campaign_next_level")
        if next_level is None:
            return None

        return self.startCampaignLevel(next_level)