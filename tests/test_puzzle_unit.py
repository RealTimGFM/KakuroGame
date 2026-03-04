# What it does: Tests the Puzzle class checkSeed (reject invalid seed, accept valid seed only if it exists in DB).
# Expected outcome: Bad seed returns False/None; valid seed in DB returns True and returns the same seed.
from puzzle import Puzzle


def test_checkSeed_rejects_invalid_seed(db):
    p = Puzzle(db)
    assert p.checkSeed("not-a-seed") is False
    assert p.displayPuzzle() is None


def test_checkSeed_accepts_seed_if_in_db(db, seed_code):
    con = db.get_connection()
    cur = con.cursor()
    cur.execute(
        "INSERT INTO puzzles (seed, puzzle_data, difficulty, campaign_level) VALUES (?, ?, ?, ?)",
        (seed_code, "{}", "easy", 1)
    )
    con.commit()
    con.close()

    p = Puzzle(db)
    assert p.checkSeed(seed_code) is True
    payload = p.displayPuzzle()
    assert payload is not None
    assert payload["seed"] == seed_code