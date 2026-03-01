from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from database import Database
from registered_user import RegisteredUser
from progression import Progression
import os
from puzzle_importer import import_puzzles_from_file

def create_app(db_path=None, testing=False):
    app = Flask(__name__)
    app.secret_key = "kakuro_secret_key_2026"

    if testing:
        app.config["TESTING"] = True
        app.secret_key = "test_secret"

    db = Database(db_path=db_path)
    db.create_tables()
    if not testing:
        import_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "puzzles_import.json")
        import_puzzles_from_file(db, import_path)

    app.config["DB_PATH"] = db.db_path

    user_service = RegisteredUser(db)
    progression_service = Progression(db)

    @app.route("/")
    def home():
        if "user_id" in session or session.get("is_guest") is True:
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
        if "user_id" not in session and session.get("is_guest") is not True:
            return redirect(url_for("login"))

        return render_template(
            "dashboard.html",
            username=session.get("username", "Guest"),
            is_guest=(session.get("is_guest") is True)
        )
    @app.route("/logout")
    def logout():
        session.clear()
        flash("You have been logged out.", "success")
        return redirect(url_for("login"))

    # Load specific puzzle (guest + registered)
    @app.route("/api/puzzle", methods=["GET"])
    def api_puzzle():
        seed = request.args.get("seed", "")
        payload = progression_service.enterPuzzleSeed(seed)
        if payload is None:
            return jsonify({"ok": False, "error": "Seed not found (or invalid)."}), 404
        return jsonify({"ok": True, "puzzle": payload})

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)