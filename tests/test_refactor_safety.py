# What it does: Protects behavior before helper-method cleanup/refactor.
# Expected outcome: If helper logic is correctly inlined, these tests still pass.

import json

from campaign import Campaign
from progression import Progression
from puzzle import Puzzle
from tests.conftest import insert_puzzle_with_solution


def _signup_and_login(client, username="tim", email="tim@test.com", password="123456"):
    client.post(
        "/signup",
        data={
            "username": username,
            "email": email,
            "password": password,
            "confirm_password": password,
        },
    )


def _make_campaign_puzzle_data(stage="Learner", level=1):
    return json.dumps(
        {
            "schema": 1,
            "v": 1,
            "w": 3,
            "h": 3,
            "stage": stage,
            "level": level,
            "clues": [".", "11/0", "3/0", "0/3", ".", ".", "0/11", ".", "."],
            "mask": "111100100",
        },
        separators=(",", ":"),
    )


def _insert_campaign_puzzle_with_solution(db, seed, stage="Learner", level=1):
    puzzle_data = _make_campaign_puzzle_data(stage=stage, level=level)

    con = db.get_connection()
    cur = con.cursor()
    cur.execute(
        "INSERT INTO puzzles (seed, puzzle_data, difficulty, campaign_level) VALUES (?, ?, ?, ?)",
        (seed, puzzle_data, stage, level),
    )
    cur.execute(
        "INSERT INTO puzzle_solutions (seed, solution_data) VALUES (?, ?)",
        (
            seed,
            json.dumps(
                {
                    "schema": 1,
                    "v": 1,
                    "w": 3,
                    "h": 3,
                    "digits": "....21.92",
                },
                separators=(",", ":"),
            ),
        ),
    )
    con.commit()
    con.close()


def test_enterPuzzleSeed_clears_campaign_state_and_switches_mode(app, db, seed_code):
    insert_puzzle_with_solution(db, seed_code)

    user_id = db.create_user("tim", "tim@test.com", "hash")

    prog = Progression(db)

    with app.test_request_context("/"):
        from flask import session

        session["user_id"] = user_id
        session["username"] = "tim"

        session["campaign_active"] = True
        session["campaign_started_at"] = 123.0
        session["campaign_elapsed_time"] = 9.5
        session["campaign_current_difficulty"] = "Intermediate"
        session["campaign_current_level"] = 4
        session["campaign_current_seed"] = "oldseed"
        session["campaign_completed_levels"] = ["Learner:1"]
        session["campaign_seen_seeds"] = ["oldseed"]
        session["campaign_last_message"] = "old"
        session["play_context"] = "campaign"

        payload = prog.enterPuzzleSeed(seed_code)

        assert payload is not None
        assert payload["seed"] == seed_code

        assert "campaign_active" not in session
        assert "campaign_started_at" not in session
        assert "campaign_elapsed_time" not in session
        assert "campaign_current_difficulty" not in session
        assert "campaign_current_level" not in session
        assert "campaign_current_seed" not in session
        assert "campaign_completed_levels" not in session
        assert "campaign_seen_seeds" not in session
        assert "campaign_last_message" not in session
        assert "play_context" not in session

    row = db.get_progression(user_id)
    assert row is not None
    assert row["mode"] == "Single Puzzle"


def test_completeSeededPuzzle_clears_seeded_state_and_resets_guest_defaults(app, db):
    prog = Progression(db)

    with app.test_request_context("/"):
        from flask import session

        session["is_guest"] = True
        session["username"] = "Guest"

        session["seeded_puzzle_seed"] = "3fu9a4"
        session["seeded_puzzle_board"] = {"4": "2"}
        session["seeded_puzzle_invalid_positions"] = [4]
        session["seeded_puzzle_locked"] = True
        session["seeded_puzzle_started_at"] = 10.0
        session["seeded_puzzle_stopped_at"] = 15.0
        session["seeded_puzzle_elapsed_time"] = 5.0
        session["seeded_puzzle_result"] = "done"
        session["seeded_puzzle_result_type"] = "success"

        session["campaign_active"] = True
        session["campaign_current_difficulty"] = "Intermediate"
        session["campaign_current_level"] = 3
        session["campaign_current_seed"] = "abc123"
        session["campaign_completed_levels"] = ["Learner:1"]
        session["campaign_seen_seeds"] = ["abc123"]
        session["campaign_last_message"] = "old"
        session["play_context"] = "campaign"

        prog.completeSeededPuzzle()

        assert "seeded_puzzle_seed" not in session
        assert "seeded_puzzle_board" not in session
        assert "seeded_puzzle_invalid_positions" not in session
        assert "seeded_puzzle_locked" not in session
        assert "seeded_puzzle_started_at" not in session
        assert "seeded_puzzle_stopped_at" not in session
        assert "seeded_puzzle_elapsed_time" not in session
        assert "seeded_puzzle_result" not in session
        assert "seeded_puzzle_result_type" not in session

        assert "campaign_active" not in session
        assert "campaign_current_difficulty" not in session
        assert "campaign_current_level" not in session
        assert "campaign_current_seed" not in session
        assert "campaign_completed_levels" not in session
        assert "campaign_seen_seeds" not in session
        assert "campaign_last_message" not in session

        assert session["guest_mode"] == "Campaign"
        assert session["guest_difficulty"] == "Learner"
        assert session["guest_level"] == 1


def test_campaign_startRun_resets_old_campaign_keys(app, db):
    camp = Campaign(db)

    with app.test_request_context("/"):
        from flask import session

        session["campaign_current_difficulty"] = "Master"
        session["campaign_current_level"] = 9
        session["campaign_current_seed"] = "oldseed"
        session["campaign_completed_levels"] = ["x"]
        session["campaign_seen_seeds"] = ["y"]
        session["campaign_last_message"] = "old"
        session["campaign_elapsed_time"] = 99.0

        camp.startRun()

        assert session["campaign_active"] is True
        assert session["play_context"] == "campaign"
        assert session["campaign_completed_levels"] == []
        assert session["campaign_seen_seeds"] == []
        assert "campaign_started_at" in session
        assert "campaign_current_seed" not in session
        assert "campaign_last_message" not in session


def test_campaign_loadNextLevel_moves_to_next_difficulty_and_level(app, db):
    _insert_campaign_puzzle_with_solution(db, "lrn002", stage="Learner", level=2)
    _insert_campaign_puzzle_with_solution(db, "int001", stage="Intermediate", level=1)

    camp = Campaign(db)

    with app.test_request_context("/"):
        from flask import session

        session["campaign_current_difficulty"] = "Learner"
        session["campaign_current_level"] = 2
        session["campaign_seen_seeds"] = []

        payload = camp.loadNextLevel()

        assert payload is not None
        assert payload["seed"] == "int001"
        assert session["campaign_current_difficulty"] == "Intermediate"
        assert session["campaign_current_level"] == 1
        assert session["campaign_current_seed"] == "int001"


def test_loadPuzzle_resets_old_seeded_state_before_loading_new_puzzle(
    app, db, seed_code
):
    insert_puzzle_with_solution(db, seed_code)
    p = Puzzle(db)

    with app.test_request_context("/"):
        from flask import session

        session["seeded_puzzle_board"] = {"4": "9"}
        session["seeded_puzzle_invalid_positions"] = [4]
        session["seeded_puzzle_locked"] = True
        session["seeded_puzzle_stopped_at"] = 100.0
        session["seeded_puzzle_elapsed_time"] = 22.0
        session["seeded_puzzle_result"] = "old"
        session["seeded_puzzle_result_type"] = "success"

        payload = p.loadPuzzle(seed_code)

        assert payload is not None
        assert session["seeded_puzzle_seed"] == seed_code
        assert "seeded_puzzle_started_at" in session
        assert "seeded_puzzle_board" not in session
        assert "seeded_puzzle_invalid_positions" not in session
        assert "seeded_puzzle_locked" not in session
        assert "seeded_puzzle_stopped_at" not in session
        assert "seeded_puzzle_elapsed_time" not in session
        assert "seeded_puzzle_result" not in session
        assert "seeded_puzzle_result_type" not in session


def test_fillCells_self_heals_broken_session_state(client, db, seed_code):
    insert_puzzle_with_solution(db, seed_code)
    _signup_and_login(client)
    client.post("/seed", data={"seed": seed_code})

    with client.session_transaction() as sess:
        sess["seeded_puzzle_board"] = "bad"
        sess["seeded_puzzle_invalid_positions"] = "bad"
        sess["seeded_puzzle_locked"] = False
        sess["seeded_puzzle_started_at"] = None

    r = client.post("/seed/fill", json={"position": 4, "value": "2"})
    assert r.status_code == 200

    j = r.get_json()
    assert j["ok"] is True
    assert j["value"] == "2"

    with client.session_transaction() as sess:
        assert isinstance(sess["seeded_puzzle_board"], dict)
        assert sess["seeded_puzzle_board"]["4"] == "2"
        assert isinstance(sess["seeded_puzzle_invalid_positions"], list)
        assert "seeded_puzzle_started_at" in sess
