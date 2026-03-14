# What it does: Tests DB completion check and puzzle check route for solved vs unsolved board.
# Expected outcome: Incomplete board stays unlocked; solved board locks and stores result.
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


def test_check_puzzle_not_completed_shows_message(client, db, seed_code):
    insert_puzzle_with_solution(db, seed_code)
    _login_and_seed(client, seed_code)

    client.post("/seed/fill", json={"position": 4, "value": "2"})
    r = client.post("/seed/check", follow_redirects=True)
    assert r.status_code == 200
    assert b"not complete yet" in r.data.lower()


def test_check_puzzle_completed_locks_board(client, db, seed_code):
    insert_puzzle_with_solution(db, seed_code)
    _login_and_seed(client, seed_code)

    client.post("/seed/fill", json={"position": 4, "value": "2"})
    client.post("/seed/fill", json={"position": 5, "value": "1"})
    client.post("/seed/fill", json={"position": 7, "value": "9"})
    client.post("/seed/fill", json={"position": 8, "value": "2"})
    r = client.post("/seed/check", follow_redirects=True)
    assert r.status_code == 200
    assert b"puzzle completed" in r.data.lower()

    with client.session_transaction() as sess:
        assert sess.get("seeded_puzzle_locked") is True
        assert sess.get("seeded_puzzle_elapsed_time") is not None