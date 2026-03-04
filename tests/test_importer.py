# What it does: Tests the JSON importer that stores puzzle data and solution data in separate tables.
# Expected outcome: puzzles.puzzle_data has no "digits", and puzzle_solutions.solution_data contains "digits".
import json
from puzzle_importer import import_puzzles_from_file, derive_seed_from_v


def test_importer_inserts_puzzle_and_solution_separately(tmp_path, db):
    data = {
        "puzzles": [
            {
                "v": 123,
                "w": 2,
                "h": 2,
                "stage": "Learner",
                "level": 1,
                "p": [
                    ". 0/3",
                    "0/4 ."
                ],
                "s": [
                    ". .",
                    ". 1"
                ]
            }
        ]
    }

    f = tmp_path / "puzzles_import.json"
    f.write_text(json.dumps(data), encoding="utf-8")

    import_puzzles_from_file(db, str(f))

    seed = derive_seed_from_v(123)

    con = db.get_connection()
    cur = con.cursor()

    cur.execute("SELECT puzzle_data FROM puzzles WHERE seed = ?", (seed,))
    p_row = cur.fetchone()
    assert p_row is not None
    assert "digits" not in p_row["puzzle_data"]

    cur.execute("SELECT solution_data FROM puzzle_solutions WHERE seed = ?", (seed,))
    s_row = cur.fetchone()
    assert s_row is not None
    assert "digits" in s_row["solution_data"]

    con.close()