from database import Database


def _signup(client, username="tim", email="tim@test.com", password="123456"):
    client.post(
        "/signup",
        data={
            "username": username,
            "email": email,
            "password": password,
            "confirm_password": password,
        },
    )


def test_username_change_updates_existing_leaderboard_rows(client):
    _signup(client)

    db = Database(db_path=client.application.config["DB_PATH"])
    with client.session_transaction() as sess:
        user_id = sess["user_id"]

    con = db.get_connection()
    cur = con.cursor()
    cur.execute(
        """
        INSERT INTO puzzles (seed, puzzle_data, difficulty, campaign_level)
        VALUES (?, ?, ?, ?)
        """,
        ("3fu9a4", "{}", "Learner", 1),
    )
    cur.execute(
        """
        INSERT INTO leaderboard (seed, user_id, username, elapsed_time)
        VALUES (?, ?, ?, ?)
        """,
        ("3fu9a4", user_id, "tim", 12.34),
    )
    cur.execute(
        """
        INSERT INTO campaign_leaderboard (user_id, username, elapsed_time)
        VALUES (?, ?, ?)
        """,
        (user_id, "tim", 98.76),
    )
    con.commit()
    con.close()

    resp = client.post(
        "/settings/username",
        data={"username": "newname"},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)

    puzzle_rows = db.get_leaderboard_by_seed("3fu9a4")
    campaign_rows = db.get_campaign_leaderboard()

    assert puzzle_rows[0]["username"] == "newname"
    assert campaign_rows[0]["username"] == "newname"
