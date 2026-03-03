# What it does: Tests /api/puzzle for both guest and logged-in user, and tests guest progress migration on signup.
# Expected outcome: Guest stores seed in session; user stores seed in user_puzzles; signup moves guest seeds to DB.
from tests.conftest import insert_puzzle

def test_guest_can_load_puzzle_and_it_stores_in_guest_session(client, db, seed_uuid):
    insert_puzzle(db, seed_uuid, "{}")

    r = client.get(f"/api/puzzle?seed={seed_uuid}")
    assert r.status_code == 200
    j = r.get_json()
    assert j["ok"] is True
    assert j["puzzle"]["seed"] == seed_uuid

    # guest session should track played puzzles
    with client.session_transaction() as sess:
        assert "user_id" not in sess
        assert seed_uuid in sess.get("guest_games", [])


def test_registered_user_load_puzzle_records_user_puzzles(client, db, seed_uuid):
    insert_puzzle(db, seed_uuid, "{}")

    client.post("/signup", data={
        "username": "u3",
        "email": "u3@test.com",
        "password": "123456",
        "confirm_password": "123456",
    })

    r = client.get(f"/api/puzzle?seed={seed_uuid}")
    assert r.status_code == 200

    # verify DB recorded it
    con = db.get_connection()
    cur = con.cursor()
    cur.execute("SELECT seed FROM user_puzzles")
    rows = cur.fetchall()
    con.close()

    assert any(row["seed"] == seed_uuid for row in rows)


def test_guest_progression_migrates_to_db_on_signup(client, db, seed_uuid):
    insert_puzzle(db, seed_uuid, "{}")

    # guest plays puzzle
    client.get(f"/api/puzzle?seed={seed_uuid}")

    # signup should migrate guest_games -> user_puzzles
    client.post("/signup", data={
        "username": "u4",
        "email": "u4@test.com",
        "password": "123456",
        "confirm_password": "123456",
    })

    con = db.get_connection()
    cur = con.cursor()
    cur.execute("SELECT seed FROM user_puzzles")
    rows = cur.fetchall()
    con.close()

    assert any(row["seed"] == seed_uuid for row in rows)

    # guest session should be cleared after migration
    with client.session_transaction() as sess:
        assert sess.get("guest_games") in (None, [])