from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from database import Database
from registered_user import RegisteredUser
from progression import Progression
import json as _json
from campaign import Campaign


# Parse puzzle_data JSON string and build a 2D grid list for template rendering.
# Each cell is a dict with: cell_type ("black"|"clue"|"play"),
# Returns (grid_rows, w, h) or (None, 0, 0)
def build_puzzle_grid(puzzle_data_str, board=None, invalid_positions=None, locked=False):
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
                row_cells.append({
                    "cell_type": "clue",
                    "clue_down": d_val if d_val > 0 else "",
                    "clue_right": r_val if r_val > 0 else "",
                    "row": r,
                    "col": c,
                    "flat_idx": i,
                })
            elif mask_bit == "0":
                row_cells.append({
                    "cell_type": "play",
                    "clue_down": "",
                    "clue_right": "",
                    "row": r,
                    "col": c,
                    "flat_idx": i,
                    "value": board.get(str(i), ""),
                    "is_invalid": i in invalid_positions,
                    "is_locked": locked,
                })
            else:
                row_cells.append({
                    "cell_type": "black",
                    "clue_down": "",
                    "clue_right": "",
                    "row": r,
                    "col": c,
                    "flat_idx": i,
                })
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
    campaign_service = Campaign(db, progression_service)

    # Return True if the current session belongs to an authenticated user or a guest.
    def _is_authenticated():
        if session.get("is_guest") is True:
            return True

        uid = session.get("user_id")
        if isinstance(uid, int):
            user = db.getUserInfo(uid)
            if user is not None:
                return True

            # stale session after db reset or deleted account
            session.pop("user_id", None)
            session.pop("username", None)

        return False
    @app.route("/")
    def home():
        if _is_authenticated():
            return redirect(url_for("dashboard"))
        return redirect(url_for("login"))

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

            user_id = user_service.createAccount(username, email, password, confirm_password)
            if user_id is not None:
                progression_service.loadProgression(user_id)
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
            current_campaign_level=progression_service.getOfficialCampaignLevel(),
        )

    @app.route("/logout")
    def logout():
        session.clear()
        flash("You have been logged out.", "success")
        session.clear()
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
                return render_template(
                    "seed_entry.html",
                    error="seed not found",
                    seed_value=seed,
                    show_guest_popup=False,
                    pending_seed=None,
                )

            seed_norm = p.displayPuzzle()["seed"]

            if session.get("is_guest") is True:
                return render_template(
                    "seed_entry.html",
                    error=None,
                    seed_value=seed_norm,
                    show_guest_popup=True,
                    pending_seed=seed_norm,
                )

            progression_service.enterSeededMode(seed_norm)
            return redirect(url_for("seed_play"))

        return render_template(
            "seed_entry.html",
            error=None,
            seed_value="",
            show_guest_popup=False,
            pending_seed=None,
        )

    # Guest confirms loading the seed from the popup.
    @app.route("/seed/confirm", methods=["POST"])
    def seed_confirm():
        if not _is_authenticated():
            return redirect(url_for("login"))

        seed = request.form.get("seed", "").strip()
        if not seed:
            return redirect(url_for("seed_entry"))

        progression_service.enterSeededMode(seed)
        return redirect(url_for("seed_play"))

    # Show the seeded puzzle play page.
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
            )

        puzzle = p.displayPuzzle()
        p.ensurePlayState()
        play_summary = p.getPlaySummary()
        grid, grid_w, grid_h = build_puzzle_grid(
            puzzle["puzzle_data"],
            board=play_summary["board"],
            invalid_positions=play_summary["invalid_positions"],
            locked=play_summary["locked"],
        )
        leaderboard_rows = db.get_leaderboard_by_seed(seed)
        return render_template(
            "seed_play.html",
            error=None,
            puzzle=puzzle,
            grid=grid,
            grid_w=grid_w,
            grid_h=grid_h,
            result_message=play_summary["result"],
            result_type=play_summary["result_type"],
            elapsed_time=play_summary["elapsed_time"],
            leaderboard_rows=leaderboard_rows,
            locked=play_summary["locked"],
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
            p.checkPuzzle(progression_service)
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

    # Start or resume campaign mode.
    @app.route("/campaign/start", methods=["GET"])
    def campaign_start():
        if not _is_authenticated():
            return redirect(url_for("login"))

        payload = campaign_service.startCampaign()
        if payload is None:
            return redirect(url_for("dashboard"))
        return redirect(url_for("campaign_play"))

    # Show the campaign puzzle page.
    @app.route("/campaign/play", methods=["GET"])
    def campaign_play():
        if not _is_authenticated():
            return redirect(url_for("login"))

        seed = session.get("campaign_puzzle_seed")
        if not seed:
            return redirect(url_for("dashboard"))

        from puzzle import Puzzle
        p = Puzzle(db)
        if not p.checkSeed(seed):
            return render_template(
                "campaign_play.html",
                error="level is not ready",
                puzzle=None,
                grid=None,
                grid_w=0,
                grid_h=0,
                result_message=None,
                result_type=None,
                elapsed_time=None,
                leaderboard_rows=[],
                locked=False,
                official_level=session.get("campaign_current_level", 1),
                level_info=db.get_campaign_level_info(session.get("campaign_current_level", 1)),
                next_level=session.get("campaign_next_level"),
                campaign_completed=session.get("campaign_completed", False),
                campaign_total_elapsed_time=session.get("campaign_total_elapsed_time"),
                campaign_leaderboard_rows=db.get_campaign_leaderboard_top5(),
                guest_prompt=session.get("campaign_guest_prompt", False),
                is_guest=(session.get("is_guest") is True),
            )

        puzzle = p.displayPuzzle()
        p.ensureCampaignPlayState()
        play_summary = p.getCampaignPlaySummary()
        grid, grid_w, grid_h = build_puzzle_grid(
            puzzle["puzzle_data"],
            board=play_summary["board"],
            invalid_positions=play_summary["invalid_positions"],
            locked=play_summary["locked"],
        )
        return render_template(
            "campaign_play.html",
            error=None,
            puzzle=puzzle,
            grid=grid,
            grid_w=grid_w,
            grid_h=grid_h,
            result_message=play_summary["result"],
            result_type=play_summary["result_type"],
            elapsed_time=play_summary["elapsed_time"],
            leaderboard_rows=db.get_leaderboard_by_seed(seed),
            locked=play_summary["locked"],
            official_level=session.get("campaign_current_level", 1),
            level_info=db.get_campaign_level_info(session.get("campaign_current_level", 1)),
            next_level=session.get("campaign_next_level"),
            campaign_completed=session.get("campaign_completed", False),
            campaign_total_elapsed_time=session.get("campaign_total_elapsed_time"),
            campaign_leaderboard_rows=db.get_campaign_leaderboard_top5(),
            guest_prompt=session.get("campaign_guest_prompt", False),
            is_guest=(session.get("is_guest") is True),
        )

    # Update one playable cell in the campaign puzzle.
    @app.route("/campaign/fill", methods=["POST"])
    def campaign_fill():
        if not _is_authenticated():
            return jsonify({"ok": False, "error": "auth required"}), 401

        seed = session.get("campaign_puzzle_seed")
        if not seed:
            return jsonify({"ok": False, "error": "no campaign puzzle"}), 400

        from puzzle import Puzzle
        p = Puzzle(db)
        if not p.checkSeed(seed):
            return jsonify({"ok": False, "error": "level is not ready"}), 404

        payload = request.get_json(silent=True) or request.form
        position = payload.get("position") if payload else None
        value = payload.get("value") if payload else None

        result = p.fillCampaignCells(position, value)
        code = 200 if result.get("ok") else 400
        return jsonify(result), code

    # Check the active campaign puzzle against the stored solution.
    @app.route("/campaign/check", methods=["POST"])
    def campaign_check():
        if not _is_authenticated():
            return redirect(url_for("login"))

        seed = session.get("campaign_puzzle_seed")
        if not seed:
            return redirect(url_for("dashboard"))

        from puzzle import Puzzle
        p = Puzzle(db)
        if p.checkSeed(seed):
            p.checkCampaignPuzzle(campaign_service)
        return redirect(url_for("campaign_play"))

    # Restart the current campaign level with a new puzzle if possible.
    @app.route("/campaign/restart", methods=["POST"])
    def campaign_restart():
        if not _is_authenticated():
            return redirect(url_for("login"))

        campaign_service.restartCampaignLevel()
        return redirect(url_for("campaign_play"))

    # Go to the next campaign level after a solved puzzle.
    @app.route("/campaign/next", methods=["POST"])
    def campaign_next():
        if not _is_authenticated():
            return redirect(url_for("login"))

        campaign_service.advanceCampaignAfterSolve()
        return redirect(url_for("campaign_play"))

    # Leave campaign mode and go back to the dashboard.
    @app.route("/campaign/leave", methods=["POST"])
    def campaign_leave():
        if not _is_authenticated():
            return redirect(url_for("login"))

        campaign_service.leaveCampaign()
        return redirect(url_for("dashboard"))

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)