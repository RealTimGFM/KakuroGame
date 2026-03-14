from tests.conftest import insert_puzzle_with_solution


def _signup(client, username="tim", email="tim@test.com", password="123456"):
    client.post("/signup", data={
        "username": username,
        "email": email,
        "password": password,
        "confirm_password": password,
    })


def _set_guest(client):
    client.get("/guest")


def test_campaign_start_as_guest_loads_level_1(client, db):
    insert_puzzle_with_solution(db, "aaaa11", difficulty="Learner", campaign_level=1)

    _set_guest(client)
    resp = client.get("/campaign/start", follow_redirects=False)
    assert resp.status_code in (302, 303)
    assert "/campaign/play" in resp.headers["Location"]

    with client.session_transaction() as sess:
        assert sess["campaign_current_level"] == 1
        assert sess["campaign_puzzle_seed"] == "aaaa11"
        assert sess["guest_mode"] == "Campaign"


def test_campaign_start_logged_in_resumes_saved_level(client, db):
    insert_puzzle_with_solution(db, "bbbb22", difficulty="Learner", campaign_level=2)

    _signup(client)
    with client.session_transaction() as sess:
        user_id = sess["user_id"]

    db.set_campaign_level(user_id, 2)

    client.get("/campaign/start", follow_redirects=False)
    with client.session_transaction() as sess:
        assert sess["campaign_current_level"] == 2
        assert sess["campaign_puzzle_seed"] == "bbbb22"


def test_campaign_restart_loads_different_seed_when_possible(client, db):
    insert_puzzle_with_solution(db, "cccc33", difficulty="Learner", campaign_level=1)
    insert_puzzle_with_solution(db, "dddd44", difficulty="Learner", campaign_level=1)

    _set_guest(client)
    client.get("/campaign/start")

    with client.session_transaction() as sess:
        first_seed = sess["campaign_puzzle_seed"]

    client.post("/campaign/restart", follow_redirects=False)

    with client.session_transaction() as sess:
        second_seed = sess["campaign_puzzle_seed"]

    assert first_seed != second_seed


def test_campaign_check_not_solved_keeps_same_level(client, db):
    insert_puzzle_with_solution(db, "eeee55", difficulty="Learner", campaign_level=1)

    _set_guest(client)
    client.get("/campaign/start")
    resp = client.post("/campaign/check", follow_redirects=True)

    assert resp.status_code == 200
    assert b"Not solved" in resp.data

    with client.session_transaction() as sess:
        assert sess.get("campaign_puzzle_locked") is False
        assert sess.get("campaign_current_level") == 1


def test_campaign_check_solved_unlocks_next_level_for_logged_in_user(client, db):
    insert_puzzle_with_solution(db, "ffff66", difficulty="Learner", campaign_level=1)
    insert_puzzle_with_solution(db, "gggg77", difficulty="Learner", campaign_level=2)

    _signup(client)
    client.get("/campaign/start")

    client.post("/campaign/fill", json={"position": 4, "value": "2"})
    client.post("/campaign/fill", json={"position": 5, "value": "1"})
    client.post("/campaign/fill", json={"position": 7, "value": "9"})
    client.post("/campaign/fill", json={"position": 8, "value": "2"})

    resp = client.post("/campaign/check", follow_redirects=True)
    assert resp.status_code == 200
    assert b"Solved" in resp.data
    assert b"Next Level" in resp.data

    with client.session_transaction() as sess:
        user_id = sess["user_id"]
        assert sess.get("campaign_puzzle_locked") is True
        assert sess.get("campaign_next_level") == 2

    row = db.get_progression(user_id)
    assert row["campaign_level"] == 2