from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    jsonify,
    flash,
)
from database import Database
from registered_user import RegisteredUser
from progression import Progression
import os
import json as _json
import time as _time


# Parse puzzle_data JSON string and build a 2D grid list for template rendering.
# Each cell is a dict with: cell_type ("black"|"clue"|"play"),
# Returns (grid_rows, w, h) or (None, 0, 0)
def build_puzzle_grid(
    puzzle_data_str, board=None, invalid_positions=None, locked=False
):
    try:
        pd = _json.loads(puzzle_data_str)
        w = pd["w"]
        h = pd["h"]
        clues = pd["clues"]
        mask = pd["mask"]
    except Exception:
        return None, 0, 0

    board = board or {}
    invalid_positions = set(int(x) for x in (invalid_positions or []))

    grid = []
    for r in range(h):
        row_cells = []
        for c in range(w):
            i = r * w + c
            clue_tok = clues[i]
            mask_bit = mask[i]

            if clue_tok != ".":
                parts = clue_tok.split("/")
                d_val = int(parts[0])
                r_val = int(parts[1])
                row_cells.append(
                    {
                        "cell_type": "clue",
                        "clue_down": d_val if d_val > 0 else "",
                        "clue_right": r_val if r_val > 0 else "",
                        "row": r,
                        "col": c,
                        "flat_idx": i,
                    }
                )
            elif mask_bit == "0":
                row_cells.append(
                    {
                        "cell_type": "play",
                        "clue_down": "",
                        "clue_right": "",
                        "row": r,
                        "col": c,
                        "flat_idx": i,
                        "value": board.get(str(i), ""),
                        "is_invalid": i in invalid_positions,
                        "is_locked": locked,
                    }
                )
            else:
                row_cells.append(
                    {
                        "cell_type": "black",
                        "clue_down": "",
                        "clue_right": "",
                        "row": r,
                        "col": c,
                        "flat_idx": i,
                    }
                )
        grid.append(row_cells)
    return grid, w, h


def create_app(db_path=None, testing=False):
    app = Flask(__name__)
    app.secret_key = "kakuro_secret_key_2026"

    if testing:
        app.config["TESTING"] = True
        app.secret_key = "test_secret"

    db = Database(db_path=db_path)
    db.create_tables()

    app.config["DB_PATH"] = db.db_path

    user_service = RegisteredUser(db)
    progression_service = Progression(db)

    # Return True if the current session belongs to an authenticated user or a guest.
    def _is_authenticated():
        return "user_id" in session or session.get("is_guest") is True

    def _show_post_solve_signup_prompt(seed: str) -> bool:
        return (
            session.get("is_guest") is True
            and session.get("post_solve_signup_seed") == seed
            and session.get("seeded_puzzle_locked", False) is True
            and session.get("seeded_puzzle_result_type") == "success"
        )

    def _remember_guest_campaign_finish(elapsed_time):
        # Store the guest's final eligible campaign time in session,
        # so signup can migrate it into campaign_leaderboard later.
        if session.get("is_guest") is not True:
            return

        if elapsed_time is None:
            return

        session["guest_campaign_finished_time"] = float(elapsed_time)
        session["guest_campaign_signup_prompt"] = True

    def _migrate_guest_campaign_finish_to_account(user_id: int):
        # When a guest signs up after finishing the full campaign,
        # move the stored guest campaign result into the real leaderboard.
        raw = session.get("guest_campaign_finished_time")
        if raw is None:
            session.pop("guest_campaign_signup_prompt", None)
            session.pop("post_solve_signup_seed", None)
            return

        try:
            elapsed_time = float(raw)
        except Exception:
            session.pop("guest_campaign_finished_time", None)
            session.pop("guest_campaign_signup_prompt", None)
            session.pop("post_solve_signup_seed", None)
            return

        db.compareCampaignTime(user_id, elapsed_time)

        session.pop("guest_campaign_finished_time", None)
        session.pop("guest_campaign_signup_prompt", None)
        session.pop("post_solve_signup_seed", None)

        flash("Your guest campaign result was saved to your new account.", "success")

    @app.route("/")
    def home():
        if _is_authenticated():
            return redirect(url_for("dashboard"))
        return redirect(url_for("login"))

    @app.route("/campaign/play")
    def campaign_play():
        if not _is_authenticated():
            return redirect(url_for("login"))

        payload = progression_service.playCampaign()
        if payload is None:
            flash("No campaign puzzle was found for your current level.", "error")
            return redirect(url_for("dashboard"))

        return redirect(url_for("seed_play"))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            email = request.form.get("email", "")
            password = request.form.get("password", "")
            ok = user_service.login(email, password)
            if ok:
                return redirect(url_for("dashboard"))
            return redirect(url_for("login"))
        return render_template("login.html")

    @app.route("/signup", methods=["GET", "POST"])
    def signup():
        if request.method == "POST":
            username = request.form.get("username", "")
            email = request.form.get("email", "")
            password = request.form.get("password", "")
            confirm_password = request.form.get("confirm_password", "")

            user_id = user_service.createAccount(
                username, email, password, confirm_password
            )
            if user_id is not None:
                progression_service.loadProgression(user_id)
                _migrate_guest_campaign_finish_to_account(user_id)
                return redirect(url_for("dashboard"))
            return redirect(url_for("signup"))

        return render_template("signup.html")

    @app.route("/guest")
    def play_guest():
        session["is_guest"] = True
        session["username"] = "Guest"
        return redirect(url_for("dashboard"))

    @app.route("/dashboard")
    def dashboard():
        if not _is_authenticated():
            return redirect(url_for("login"))

        return render_template(
            "dashboard.html",
            username=session.get("username", "Guest"),
            is_guest=(session.get("is_guest") is True),
            seeded_puzzle_seed=session.get("seeded_puzzle_seed"),
            guest_campaign_signup_prompt=(
                session.get("is_guest") is True
                and session.get("guest_campaign_signup_prompt") is True
            ),
            guest_campaign_finished_time=session.get("guest_campaign_finished_time"),
        )

    @app.route("/logout")
    def logout():
        session.clear()
        flash("You have been logged out.", "success")
        return redirect(url_for("login"))

    # Load specific puzzle by seed (guest + registered) — JSON API.
    @app.route("/api/puzzle", methods=["GET"])
    def api_puzzle():
        seed = request.args.get("seed", "")
        payload = progression_service.enterPuzzleSeed(seed)
        if payload is None:
            return jsonify({"ok": False, "error": "Seed not found (or invalid)."}), 404
        return jsonify({"ok": True, "puzzle": payload})

    # Show the seed entry form (GET) or validate a submitted seed (POST).
    @app.route("/seed", methods=["GET", "POST"])
    def seed_entry():
        if not _is_authenticated():
            return redirect(url_for("login"))

        if request.method == "POST":
            seed = request.form.get("seed", "").strip()
            from puzzle import Puzzle

            p = Puzzle(db)
            if not p.checkSeed(seed):
                return render_template("seed_entry.html", error="seed not found")

            seed_norm = p.displayPuzzle()["seed"]

            if session.get("is_guest") is True:
                return redirect(url_for("seed_confirm", seed=seed_norm))
            progression_service.enterSeededMode(seed_norm)
            return redirect(url_for("seed_play"))

        return render_template("seed_entry.html", error=None)

    # Show the guest warning/confirm page before loading a seeded puzzle.
    @app.route("/seed/confirm", methods=["GET", "POST"])
    def seed_confirm():
        if not _is_authenticated():
            return redirect(url_for("login"))

        seed = request.args.get("seed") or request.form.get("seed", "")

        if request.method == "POST":
            progression_service.enterSeededMode(seed)
            return redirect(url_for("seed_play"))

        return render_template("seed_confirm.html", seed=seed)

    # Show the seeded puzzle play page.
    # Reads the seed from session, fetches puzzle data from DB,
    # parses puzzle_data JSON and builds the 2D grid for the template.
    @app.route("/seed/play", methods=["GET"])
    def seed_play():
        if not _is_authenticated():
            return redirect(url_for("login"))

        seed = session.get("seeded_puzzle_seed")
        if not seed:
            return redirect(url_for("dashboard"))

        from puzzle import Puzzle

        p = Puzzle(db)
        if not p.checkSeed(seed):
            return render_template(
                "seed_play.html",
                error="seed not found",
                puzzle=None,
                grid=None,
                grid_w=0,
                grid_h=0,
                result_message=None,
                result_type=None,
                elapsed_time=None,
                leaderboard_rows=[],
                locked=False,
                campaign_active=False,
                campaign_level=None,
                campaign_total_levels=None,
                campaign_difficulty=None,
                is_guest=(session.get("is_guest") is True),
                show_post_solve_signup_prompt=False,
                warn_before_leave=False,
            )

        puzzle = p.displayPuzzle()

        if session.get("seeded_puzzle_started_at") is None:
            session["seeded_puzzle_started_at"] = _time.time()

        board = session.get("seeded_puzzle_board", {})
        if not isinstance(board, dict):
            board = {}
            session["seeded_puzzle_board"] = board

        invalid_positions = session.get("seeded_puzzle_invalid_positions", [])
        if not isinstance(invalid_positions, list):
            invalid_positions = []
            session["seeded_puzzle_invalid_positions"] = invalid_positions

        locked = session.get("seeded_puzzle_locked", False) is True
        result_message = session.get("seeded_puzzle_result")
        result_type = session.get("seeded_puzzle_result_type")
        elapsed_time = session.get("seeded_puzzle_elapsed_time")
        campaign_active = session.get("play_context") == "campaign"
        campaign_level = None
        campaign_total_levels = None
        campaign_difficulty = None

        if campaign_active:
            from campaign import Campaign

            campaign_service = Campaign(db)
            campaign_difficulty = campaign_service.normalizeDifficulty(
                session.get("campaign_current_difficulty", "Learner")
            )
            current_level = int(session.get("campaign_current_level", 1) or 1)

            campaign_level = (
                f"{campaign_service.DIFFICULTIES.index(campaign_difficulty) + 1}-"
                f"{int(current_level)}"
            )
            campaign_total_levels = db.get_max_campaign_level_for_difficulty(
                campaign_difficulty
            )

        grid, grid_w, grid_h = build_puzzle_grid(
            puzzle["puzzle_data"],
            board=board,
            invalid_positions=invalid_positions,
            locked=locked,
        )

        show_leaderboard = not (
            locked is True and result_type != "success"
        )
        leaderboard_rows = db.get_leaderboard_by_seed(seed) if show_leaderboard else []

        return render_template(
            "seed_play.html",
            error=None,
            puzzle=puzzle,
            grid=grid,
            grid_w=grid_w,
            grid_h=grid_h,
            result_message=result_message,
            result_type=result_type,
            elapsed_time=elapsed_time,
            leaderboard_rows=leaderboard_rows,
            locked=locked,
            campaign_active=campaign_active,
            campaign_level=campaign_level,
            campaign_total_levels=campaign_total_levels,
            campaign_difficulty=campaign_difficulty,
            is_guest=(session.get("is_guest") is True),
            show_post_solve_signup_prompt=_show_post_solve_signup_prompt(seed),
            warn_before_leave=(locked is not True),
        )

    # Update one playable cell in the seeded puzzle.
    @app.route("/seed/fill", methods=["POST"])
    def seed_fill():
        if not _is_authenticated():
            return jsonify({"ok": False, "error": "auth required"}), 401

        seed = session.get("seeded_puzzle_seed")
        if not seed:
            return jsonify({"ok": False, "error": "no seeded puzzle"}), 400

        from puzzle import Puzzle

        p = Puzzle(db)
        if not p.checkSeed(seed):
            return jsonify({"ok": False, "error": "seed not found"}), 404

        payload = request.get_json(silent=True) or request.form
        position = payload.get("position") if payload else None
        value = payload.get("value") if payload else None

        result = p.fillCells(position, value)
        code = 200 if result.get("ok") else 400
        return jsonify(result), code

    # Check the seeded puzzle against the stored solution.
    @app.route("/seed/check", methods=["POST"])
    def seed_check():
        if not _is_authenticated():
            return redirect(url_for("login"))

        seed = session.get("seeded_puzzle_seed")
        if not seed:
            return redirect(url_for("dashboard"))

        from puzzle import Puzzle

        p = Puzzle(db)

        if p.checkSeed(seed):
            if request.form.get("show_solution") == "1":
                p.showSolution(progression_service)
            else:
                result = p.checkPuzzle(progression_service)

                if result.get("done"):
                    if (
                        session.get("is_guest") is True
                        and session.get("play_context") != "campaign"
                    ):
                        session["post_solve_signup_seed"] = seed

                    if session.get("play_context") == "campaign":
                        was_guest = session.get("is_guest") is True
                        was_ineligible = (
                            session.get("campaign_ineligible", False) is True
                        )

                        campaign_result = progression_service.advanceCampaign()

                        if campaign_result.get("finished"):
                            if was_guest and not was_ineligible:
                                _remember_guest_campaign_finish(
                                    campaign_result.get("elapsed_time")
                                )

                            return redirect(url_for("dashboard"))

        return redirect(url_for("seed_play"))

    @app.route("/seed/restart", methods=["POST"])
    def seed_restart():
        if not _is_authenticated():
            return redirect(url_for("login"))

        seed = session.get("seeded_puzzle_seed")
        if not seed:
            return redirect(url_for("dashboard"))

        from puzzle import Puzzle

        p = Puzzle(db)
        p.restartPuzzle()

        return redirect(url_for("seed_play"))

    # Back to Campaign: exit seeded mode and return to the dashboard.
    @app.route("/seed/back", methods=["POST"])
    def seed_back():
        if not _is_authenticated():
            return redirect(url_for("login"))
        progression_service.exitSeededMode()
        return redirect(url_for("dashboard"))

    # Complete a seeded puzzle: restore official progression and return to dashboard.
    @app.route("/seed/complete", methods=["POST"])
    def seed_complete():
        if not _is_authenticated():
            return redirect(url_for("login"))
        progression_service.completeSeededPuzzle()
        return redirect(url_for("dashboard"))

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
