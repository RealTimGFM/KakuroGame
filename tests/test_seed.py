# tests/test_seed.py

# What it does: Tests Use Case 3 — load a specific puzzle by seed (UUID).
# Covers: auth guard, bad seed error, guest confirm flow, logged-in direct load,
#         /seed/play page, Back to Campaign, post-completion progression reset,
#         is_guest clearing on login/signup, and Kakuro board grid rendering.

import json
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


# Build a minimal valid puzzle_data JSON string for a 3x3 puzzle.
# Layout matches puzzles_import.json v=1:
#   row0: black  clue(11/0)  clue(3/0)
#   row1: clue(0/3)  play  play
#   row2: clue(0/11) play  play
# mask:  1 1 1 1 0 0 1 0 0  -> "111100100"
# clues: [".","11/0","3/0","0/3",".",".",  "0/11",".","."]
def _make_puzzle_data():
    return json.dumps({
        "schema": 1,
        "v": 1,
        "w": 3,
        "h": 3,
        "stage": "Learner",
        "level": 1,
        "clues": [".", "11/0", "3/0", "0/3", ".", ".", "0/11", ".", "."],
        "mask": "111100100"
    })


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
    client.post("/seed", data={"seed": seed_uuid}, follow_redirects=False)
    resp = client.get(f"/seed/confirm?seed={seed_uuid}")
    assert resp.status_code == 200
    assert b"session" in resp.data.lower()
    assert b"sign up" in resp.data.lower()


# What it does: POST /seed/confirm as guest sets seeded_puzzle_seed in session and
#               records seed in guest_games, then redirects to /seed/play.
def test_guest_confirm_sets_seeded_session_state(client, db, seed_uuid):
    insert_puzzle(db, seed_uuid, "{}")
    _set_guest(client)
    client.post("/seed", data={"seed": seed_uuid})
    resp = client.post("/seed/confirm", data={"seed": seed_uuid}, follow_redirects=False)

    assert resp.status_code in (302, 303)
    assert "/seed/play" in resp.headers["Location"]

    with client.session_transaction() as sess:
        assert sess.get("seeded_puzzle_seed") == seed_uuid
        assert seed_uuid in sess.get("guest_games", [])


# ---------- logged-in direct load ----------

# What it does: valid seed as logged-in user sets seeded_puzzle_seed in session
#               without going through confirm, and redirects to /seed/play.
def test_valid_seed_logged_in_sets_seeded_session(client, db, seed_uuid):
    insert_puzzle(db, seed_uuid, "{}")
    _signup_and_login(client)
    resp = client.post("/seed", data={"seed": seed_uuid}, follow_redirects=False)
    assert resp.status_code in (302, 303)
    assert "/seed/play" in resp.headers["Location"]

    with client.session_transaction() as sess:
        assert sess.get("seeded_puzzle_seed") == seed_uuid


# What it does: valid seed as logged-in records the seed in user_puzzles.
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


# ---------- /seed/play page ----------

# What it does: GET /seed/play without seeded session redirects to dashboard.
def test_seed_play_requires_seeded_session(client):
    _set_guest(client)
    resp = client.get("/seed/play", follow_redirects=False)
    assert resp.status_code in (302, 303)
    assert "/dashboard" in resp.headers["Location"]


# What it does: GET /seed/play with valid seeded session returns 200 for logged-in user.
def test_seed_play_loads_for_logged_in(client, db, seed_uuid):
    insert_puzzle(db, seed_uuid, "{}")
    _signup_and_login(client)
    client.post("/seed", data={"seed": seed_uuid})
    resp = client.get("/seed/play")
    assert resp.status_code == 200


# What it does: GET /seed/play with valid seeded session returns 200 for guest.
def test_seed_play_loads_for_guest(client, db, seed_uuid):
    insert_puzzle(db, seed_uuid, "{}")
    _set_guest(client)
    client.post("/seed", data={"seed": seed_uuid})
    client.post("/seed/confirm", data={"seed": seed_uuid})
    resp = client.get("/seed/play")
    assert resp.status_code == 200


# What it does: GET /seed/play when seed is no longer in DB shows "seed not found".
def test_seed_play_shows_error_if_seed_missing_from_db(client, seed_uuid):
    _set_guest(client)
    with client.session_transaction() as sess:
        sess["seeded_puzzle_seed"] = seed_uuid
    resp = client.get("/seed/play")
    assert resp.status_code == 200
    assert b"seed not found" in resp.data.lower()


# What it does: /seed/play page includes Back to Campaign and Complete buttons.
def test_seed_play_has_back_and_complete_buttons(client, db, seed_uuid):
    insert_puzzle(db, seed_uuid, "{}")
    _signup_and_login(client)
    client.post("/seed", data={"seed": seed_uuid})
    resp = client.get("/seed/play")
    assert b"/seed/back" in resp.data
    assert b"/seed/complete" in resp.data


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

    from database import Database
    d = Database(db_path=client.application.config["DB_PATH"])
    with client.session_transaction() as sess:
        uid = sess.get("user_id")
    row = d.get_progression(uid)
    assert row["mode"] == "Campaign"


# ---------- is_guest cleared on auth ----------

# What it does: logging in as a registered user removes is_guest from session.
def test_login_clears_is_guest(client):
    client.post("/signup", data={
        "username": "guser",
        "email": "guser@test.com",
        "password": "123456",
        "confirm_password": "123456",
    })
    client.get("/logout")
    client.get("/guest")

    with client.session_transaction() as sess:
        assert sess.get("is_guest") is True

    client.post("/login", data={"email": "guser@test.com", "password": "123456"})

    with client.session_transaction() as sess:
        assert "is_guest" not in sess
        assert "user_id" in sess


# What it does: signing up as a new user removes is_guest from session.
def test_signup_clears_is_guest(client):
    client.get("/guest")

    with client.session_transaction() as sess:
        assert sess.get("is_guest") is True

    client.post("/signup", data={
        "username": "newbie",
        "email": "newbie@test.com",
        "password": "123456",
        "confirm_password": "123456",
    })

    with client.session_transaction() as sess:
        assert "is_guest" not in sess
        assert "user_id" in sess


# ---------- Kakuro board grid rendering tests ----------

# What it does: GET /seed/play with a real puzzle_data returns 200 and the page
#               contains the kakuro-board grid container element.
def test_seed_play_renders_grid_container(client, db, seed_uuid):
    insert_puzzle(db, seed_uuid, _make_puzzle_data())
    _signup_and_login(client)
    client.post("/seed", data={"seed": seed_uuid})
    resp = client.get("/seed/play")
    assert resp.status_code == 200
    assert b"kakuro-board" in resp.data


# What it does: GET /seed/play with a 3x3 puzzle_data renders exactly 9 <td> cells (w*h).
def test_seed_play_renders_correct_number_of_cells(client, db, seed_uuid):
    insert_puzzle(db, seed_uuid, _make_puzzle_data())
    _signup_and_login(client)
    client.post("/seed", data={"seed": seed_uuid})
    resp = client.get("/seed/play")
    assert resp.status_code == 200
    # 3x3 = 9 cells, each rendered as a <td>
    assert resp.data.count(b"<td") == 9


# What it does: GET /seed/play with a puzzle that has playable cells includes
#               at least one <input> element with class kc-input.
def test_seed_play_renders_playable_inputs(client, db, seed_uuid):
    insert_puzzle(db, seed_uuid, _make_puzzle_data())
    _signup_and_login(client)
    client.post("/seed", data={"seed": seed_uuid})
    resp = client.get("/seed/play")
    assert resp.status_code == 200
    assert b"kc-input" in resp.data
    # The 3x3 puzzle has 4 playable cells -> 4 inputs
    assert resp.data.count(b"kc-input") >= 4


# What it does: GET /seed/play renders clue tokens "11" and "3" visible on the page
#               (as the numeric parts of clue cells "11/0" and "3/0").
def test_seed_play_renders_clue_values(client, db, seed_uuid):
    insert_puzzle(db, seed_uuid, _make_puzzle_data())
    _signup_and_login(client)
    client.post("/seed", data={"seed": seed_uuid})
    resp = client.get("/seed/play")
    assert resp.status_code == 200
    # clue "11/0": down=11 visible, right side is 0 so blank
    assert b">11<" in resp.data
    # clue "3/0": down=3 visible
    assert b">3<" in resp.data
    # clue "0/3": right=3 visible
    assert b">3<" in resp.data
    # clue "0/11": right=11 visible
    assert b">11<" in resp.data


# What it does: GET /seed/play must NOT expose solution digits or the word "solution"
#               anywhere in the page HTML.
def test_seed_play_does_not_expose_solution(client, db, seed_uuid):
    pd_str = _make_puzzle_data()
    insert_puzzle(db, seed_uuid, pd_str)

    # Insert a fake solution row to ensure the route never leaks it
    con = db.get_connection()
    cur = con.cursor()
    cur.execute(
        "INSERT INTO puzzle_solutions (seed, solution_data) VALUES (?, ?)",
        (seed_uuid, json.dumps({"digits": "...291..92"}))
    )
    con.commit()
    con.close()

    _signup_and_login(client)
    client.post("/seed", data={"seed": seed_uuid})
    resp = client.get("/seed/play")
    assert resp.status_code == 200

    html = resp.data.lower()
    assert b"solution" not in html
    assert b"puzzle_solutions" not in html
    # Known solution digits "291" or "92" must not appear as a sequence in the HTML
    assert b"291" not in resp.data
