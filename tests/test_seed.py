# tests/test_seed.py

# What it does: Tests Use Case 3 — load a specific puzzle by seed (UUID).
# Covers: auth guard, bad seed error, guest confirm flow, logged-in direct load,
#         Back to Campaign, and post-completion progression reset.

import pytest
from tests.conftest import insert_puzzle


# ---------- helpers ----------

def _signup_and_login(client, username="tim", email="tim@test.com", password="123456"):
    client.post("/signup", data={
        "username": username,
        "email": email,
        "password": password,
        "confirm_password": password,
    })


def _set_guest(client):
    client.get("/guest")


# ---------- auth guard ----------

# What it does: unauthenticated GET /seed must redirect to login.
def test_seed_page_requires_auth(client):
    resp = client.get("/seed", follow_redirects=False)
    assert resp.status_code in (302, 303)
    assert "/login" in resp.headers["Location"]


# What it does: guest can reach GET /seed.
def test_seed_page_accessible_as_guest(client):
    _set_guest(client)
    resp = client.get("/seed")
    assert resp.status_code == 200


# What it does: logged-in user can reach GET /seed.
def test_seed_page_accessible_as_logged_in(client):
    _signup_and_login(client)
    resp = client.get("/seed")
    assert resp.status_code == 200


# ---------- bad seed ----------

# What it does: POST /seed with a non-UUID string shows exactly "seed not found".
def test_bad_seed_string_shows_error(client):
    _set_guest(client)
    resp = client.post("/seed", data={"seed": "not-a-uuid"}, follow_redirects=True)
    assert resp.status_code == 200
    assert b"seed not found" in resp.data.lower()


# What it does: POST /seed with a valid UUID that is not in the DB shows "seed not found".
def test_seed_not_in_db_shows_error(client, seed_uuid):
    _set_guest(client)
    resp = client.post("/seed", data={"seed": seed_uuid}, follow_redirects=True)
    assert resp.status_code == 200
    assert b"seed not found" in resp.data.lower()


# ---------- guest confirm flow ----------

# What it does: valid seed as guest redirects to /seed/confirm (not directly loading).
def test_valid_seed_guest_redirects_to_confirm(client, db, seed_uuid):
    insert_puzzle(db, seed_uuid, "{}")
    _set_guest(client)
    resp = client.post("/seed", data={"seed": seed_uuid}, follow_redirects=False)
    assert resp.status_code in (302, 303)
    assert "/seed/confirm" in resp.headers["Location"]


# What it does: GET /seed/confirm shows guest warning text and a Sign Up link.
def test_seed_confirm_page_shows_warning_and_signup(client, db, seed_uuid):
    insert_puzzle(db, seed_uuid, "{}")
    _set_guest(client)
    # arrive via POST /seed
    client.post("/seed", data={"seed": seed_uuid}, follow_redirects=False)
    resp = client.get(f"/seed/confirm?seed={seed_uuid}")
    assert resp.status_code == 200
    assert b"session" in resp.data.lower()        # warns about session-only progress
    assert b"sign up" in resp.data.lower()        # Sign Up option present


# What it does: POST /seed/confirm as guest sets seeded_puzzle_seed in session and
#               records seed in guest_games.
def test_guest_confirm_sets_seeded_session_state(client, db, seed_uuid):
    insert_puzzle(db, seed_uuid, "{}")
    _set_guest(client)
    client.post("/seed", data={"seed": seed_uuid})
    client.post("/seed/confirm", data={"seed": seed_uuid}, follow_redirects=False)

    with client.session_transaction() as sess:
        assert sess.get("seeded_puzzle_seed") == seed_uuid
        assert seed_uuid in sess.get("guest_games", [])


# ---------- logged-in direct load ----------

# What it does: valid seed as logged-in user sets seeded_puzzle_seed in session
#               without going through confirm, and records in user_puzzles.
def test_valid_seed_logged_in_sets_seeded_session(client, db, seed_uuid):
    insert_puzzle(db, seed_uuid, "{}")
    _signup_and_login(client)
    resp = client.post("/seed", data={"seed": seed_uuid}, follow_redirects=False)
    assert resp.status_code in (302, 303)

    with client.session_transaction() as sess:
        assert sess.get("seeded_puzzle_seed") == seed_uuid


def test_valid_seed_logged_in_records_user_puzzles(client, db, seed_uuid):
    insert_puzzle(db, seed_uuid, "{}")
    _signup_and_login(client)
    client.post("/seed", data={"seed": seed_uuid})

    con = db.get_connection()
    cur = con.cursor()
    cur.execute("SELECT seed FROM user_puzzles")
    rows = cur.fetchall()
    con.close()
    assert any(row["seed"] == seed_uuid for row in rows)


# ---------- Back to Campaign ----------

# What it does: POST /seed/back clears seeded_puzzle_seed and redirects to dashboard.
def test_back_to_campaign_clears_seeded_state(client, db, seed_uuid):
    insert_puzzle(db, seed_uuid, "{}")
    _signup_and_login(client)
    client.post("/seed", data={"seed": seed_uuid})

    with client.session_transaction() as sess:
        assert sess.get("seeded_puzzle_seed") == seed_uuid

    resp = client.post("/seed/back", follow_redirects=False)
    assert resp.status_code in (302, 303)
    assert "/dashboard" in resp.headers["Location"]

    with client.session_transaction() as sess:
        assert "seeded_puzzle_seed" not in sess


# ---------- post-completion progression reset ----------

# What it does: POST /seed/complete as guest resets progression to level 1 / Campaign
#               and clears seeded_puzzle_seed.
def test_complete_seeded_puzzle_guest_resets_to_level_1(client, db, seed_uuid):
    insert_puzzle(db, seed_uuid, "{}")
    _set_guest(client)
    client.post("/seed", data={"seed": seed_uuid})
    client.post("/seed/confirm", data={"seed": seed_uuid})

    # simulate guest had advanced to level 3
    with client.session_transaction() as sess:
        sess["guest_level"] = 3

    resp = client.post("/seed/complete", follow_redirects=False)
    assert resp.status_code in (302, 303)

    with client.session_transaction() as sess:
        assert "seeded_puzzle_seed" not in sess
        assert sess.get("guest_level") == 1
        assert sess.get("guest_mode") == "Campaign"


# What it does: POST /seed/complete as logged-in restores mode to Campaign
#               and clears seeded_puzzle_seed.
def test_complete_seeded_puzzle_logged_in_restores_campaign(client, db, seed_uuid):
    insert_puzzle(db, seed_uuid, "{}")
    _signup_and_login(client)
    client.post("/seed", data={"seed": seed_uuid})

    resp = client.post("/seed/complete", follow_redirects=False)
    assert resp.status_code in (302, 303)

    with client.session_transaction() as sess:
        assert "seeded_puzzle_seed" not in sess

    # DB mode must be back to Campaign
    from database import Database
    d = Database(db_path=client.application.config["DB_PATH"])
    with client.session_transaction() as sess:
        uid = sess.get("user_id")
    row = d.get_progression(uid)
    assert row["mode"] == "Campaign"