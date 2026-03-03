# What it does: Tests the Puzzle class seedCheck (reject non-UUID, accept UUID only if it exists in DB).
# Expected outcome: Bad seed returns False/None; valid seed in DB returns True and returns the same seed.
from puzzle import Puzzle

def test_checkSeed_rejects_non_uuid(db):
    p = Puzzle(db)
    assert p.checkSeed("not-a-uuid") is False
    assert p.displayPuzzle() is None


def test_checkSeed_accepts_uuid_if_in_db(db, seed_uuid):
    # Insert puzzle first
    con = db.get_connection()
    cur = con.cursor()
    cur.execute(
        "INSERT INTO puzzles (seed, puzzle_data, difficulty, campaign_level) VALUES (?, ?, ?, ?)",
        (seed_uuid, "{}", "easy", 1)
    )
    con.commit()
    con.close()

    p = Puzzle(db)
    assert p.checkSeed(seed_uuid) is True
    payload = p.displayPuzzle()
    assert payload is not None
    assert payload["seed"] == seed_uuid