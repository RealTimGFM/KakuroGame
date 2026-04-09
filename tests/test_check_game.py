# What it does: Tests DB completion check and puzzle check route for solved vs unsolved board.
# Expected outcome: Invalid input stays unlocked and shows invalid message; wrong valid input stays unlocked; solved board locks and stores result.
from tests.conftest import insert_puzzle_with_solution


def _login_and_seed(client, seed):
    client.post("/signup", data={
        "username": "tim",
        "email": "tim@test.com",
        "password": "123456",
        "confirm_password": "123456",
    })
    client.post("/seed", data={"seed": seed})


def test_db_isCompleted_false_then_true(db, seed_code):
    insert_puzzle_with_solution(db, seed_code)

    assert db.isCompleted(seed_code, {}) is False
    assert db.isCompleted(seed_code, {"4": "2", "5": "1", "7": "9", "8": "2"}) is True


def test_check_puzzle_invalid_input_shows_invalid_message(client, db, seed_code):
    insert_puzzle_with_solution(db, seed_code)
    _login_and_seed(client, seed_code)

    client.post("/seed/fill", json={"position": 4, "value": "a"})
    r = client.post("/seed/check", follow_redirects=True)
    assert r.status_code == 200
    assert b"invalid input" in r.data.lower()

    with client.session_transaction() as sess:
        assert sess.get("seeded_puzzle_locked") is not True
        assert sess.get("seeded_puzzle_invalid_positions") == [4]


def test_check_puzzle_wrong_valid_digit_shows_not_complete(client, db, seed_code):
    insert_puzzle_with_solution(db, seed_code)
    _login_and_seed(client, seed_code)

    client.post("/seed/fill", json={"position": 4, "value": "9"})
    r = client.post("/seed/check", follow_redirects=True)
    assert r.status_code == 200
    assert b"not solved" in r.data.lower()

    with client.session_transaction() as sess:
        assert sess.get("seeded_puzzle_locked") is not True
        assert sess.get("seeded_puzzle_invalid_positions") == []


def test_check_puzzle_completed_locks_board(client, db, seed_code):
    insert_puzzle_with_solution(db, seed_code)
    _login_and_seed(client, seed_code)

    client.post("/seed/fill", json={"position": 4, "value": "2"})
    client.post("/seed/fill", json={"position": 5, "value": "1"})
    client.post("/seed/fill", json={"position": 7, "value": "9"})
    client.post("/seed/fill", json={"position": 8, "value": "2"})
    r = client.post("/seed/check", follow_redirects=True)
    assert r.status_code == 200
    assert b"solved in" in r.data.lower()

    with client.session_transaction() as sess:
        assert sess.get("seeded_puzzle_locked") is True
        assert sess.get("seeded_puzzle_elapsed_time") is not None


def test_show_solution_fills_grid_and_locks_puzzle(client, db, seed_code):
    insert_puzzle_with_solution(db, seed_code)
    _login_and_seed(client, seed_code)

    r = client.post("/seed/check", data={"show_solution": "1"}, follow_redirects=True)
    assert r.status_code == 200
    assert b"solution shown in" in r.data.lower()

    with client.session_transaction() as sess:
        assert sess.get("seeded_puzzle_locked") is True
        assert sess.get("seeded_puzzle_invalid_positions") == []
        assert sess.get("seeded_puzzle_board") == {
            "4": "2",
            "5": "1",
            "7": "9",
            "8": "2",
        }
        assert sess.get("seeded_puzzle_elapsed_time") is not None


def test_show_solution_in_campaign_flags_run_ineligible(client, db, seed_code):
    insert_puzzle_with_solution(db, seed_code)
    _login_and_seed(client, seed_code)

    with client.session_transaction() as sess:
        sess["play_context"] = "campaign"
        sess["campaign_active"] = True
        sess["campaign_ineligible"] = False

    r = client.post("/seed/check", data={"show_solution": "1"}, follow_redirects=True)
    assert r.status_code == 200

    with client.session_transaction() as sess:
        assert sess.get("campaign_ineligible") is True
        user_id = sess["user_id"]

    row = db.get_progression(user_id)
    assert int(row["campaign_ineligible"]) == 1
