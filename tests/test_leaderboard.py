# What it does: Tests user time update and leaderboard sorting/best-time behavior.
# Expected outcome: Best time is kept per user per puzzle and rows are sorted ascending.
from tests.conftest import insert_puzzle_with_solution
from leaderboard import Leaderboard


def test_updatePlayerTime_updates_user_puzzle_and_leaderboard(client, db, seed_code):
    insert_puzzle_with_solution(db, seed_code)
    client.post("/signup", data={
        "username": "tim",
        "email": "tim@test.com",
        "password": "123456",
        "confirm_password": "123456",
    })
    client.post("/seed", data={"seed": seed_code})

    from progression import Progression
    prog = Progression(db)

    with client.session_transaction() as sess:
        user_id = sess["user_id"]

    rows = prog.updatePlayerTime(seed_code, 12.5, user_id=user_id)
    assert len(rows) == 1
    assert rows[0]["username"] == "tim"
    assert float(rows[0]["elapsed_time"]) == 12.5

    con = db.get_connection()
    cur = con.cursor()
    cur.execute("SELECT last_elapsed_time, best_elapsed_time FROM user_puzzles WHERE seed = ?", (seed_code,))
    row = cur.fetchone()
    con.close()

    assert float(row["last_elapsed_time"]) == 12.5
    assert float(row["best_elapsed_time"]) == 12.5


def test_leaderboard_keeps_best_time_and_sorts(db, seed_code):
    insert_puzzle_with_solution(db, seed_code)
    u1 = db.create_user("u1", "u1@test.com", "x")
    u2 = db.create_user("u2", "u2@test.com", "x")
    db.mark_user_played_seed(u1, seed_code)
    db.mark_user_played_seed(u2, seed_code)

    lb = Leaderboard(db)
    lb.setPuzzleLeaderboard(u1, seed_code, 20.0)
    lb.setPuzzleLeaderboard(u2, seed_code, 10.0)
    rows = lb.setPuzzleLeaderboard(u1, seed_code, 15.0)

    assert [row["username"] for row in rows] == ["u2", "u1"]
    assert float(rows[1]["elapsed_time"]) == 15.0