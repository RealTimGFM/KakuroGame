# progression.py
from flask import flash, session
from typing import Optional, Dict, Any
from puzzle import Puzzle


class Progression:
    def __init__(self, db):
        self.db = db

    def displayError(self, msg: str):
        flash(msg, "error")

    def setMode(self, mode: str):
        m = (mode or "").strip()
        if m not in ("Campaign", "Single Puzzle"):
            self.displayError("Invalid mode.")
            return

        uid = session.get("user_id")
        if isinstance(uid, int):
            self.db.ensure_progression_row(uid)
            self.db.set_mode(uid, m)
        else:
            session["guest_mode"] = m

    def returnCampaign(self) -> Dict[str, Any]:
        self.setMode("Campaign")
        return {"mode": "Campaign"}

    def setLevel(self, level: int):
        try:
            lvl = int(level)
        except Exception:
            self.displayError("Invalid level.")
            return
        if lvl < 1:
            self.displayError("Invalid level.")
            return

        uid = session.get("user_id")
        if isinstance(uid, int):
            self.db.ensure_progression_row(uid)
            self.db.set_campaign_level(uid, lvl)
        else:
            session["guest_level"] = lvl

    def loadProgression(self, user_id: int):
        # Guest -> Registered migration
        self.db.ensure_progression_row(user_id)

        guest_mode = session.get("guest_mode")
        guest_level = session.get("guest_level")

        if guest_mode in ("Campaign", "Single Puzzle"):
            self.db.set_mode(user_id, guest_mode)

        if isinstance(guest_level, int) and guest_level >= 1:
            self.db.set_campaign_level(user_id, guest_level)

        guest_games = session.get("guest_games", [])
        if isinstance(guest_games, list):
            for seed in guest_games:
                if isinstance(seed, str) and self.db.get_puzzle_by_seed(seed):
                    self.db.mark_user_played_seed(user_id, seed)

        session.pop("guest_games", None)
        session.pop("guest_mode", None)
        session.pop("guest_level", None)

    def enterPuzzleSeed(self, seed: str) -> Optional[Dict[str, Any]]:
        p = Puzzle(self.db)
        if not p.checkSeed(seed):
            self.displayError("Seed not found (or invalid).")
            return None

        self.setMode("Single Puzzle")

        payload = p.displayPuzzle()
        if payload is None:
            self.displayError("Puzzle load failed.")
            return None

        seed_norm = payload["seed"]  # IMPORTANT: use normalized UUID from Puzzle

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