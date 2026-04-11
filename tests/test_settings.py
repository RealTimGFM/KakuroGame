from werkzeug.security import check_password_hash


def _signup(client, username="tim", email="tim@test.com", password="123456"):
    return client.post(
        "/signup",
        data={
            "username": username,
            "email": email,
            "password": password,
            "confirm_password": password,
        },
    )


def test_settings_page_requires_login(client):
    resp = client.get("/settings", follow_redirects=False)
    assert resp.status_code in (302, 303)
    assert "/login" in resp.headers["Location"]


def test_settings_update_routes_require_login(client):
    for path, payload in (
        ("/settings/username", {"username": "newname"}),
        ("/settings/email", {"email": "new@test.com"}),
        ("/settings/password", {"password": "abcdef"}),
    ):
        resp = client.post(path, data=payload, follow_redirects=False)
        assert resp.status_code in (302, 303)
        assert "/login" in resp.headers["Location"]


def test_settings_page_shows_current_user_info(client):
    _signup(client, username="tim", email="tim@test.com")

    resp = client.get("/settings")

    assert resp.status_code == 200
    assert b"current username" in resp.data.lower()
    assert b"tim" in resp.data
    assert b"tim@test.com" in resp.data


def test_settings_username_updates_db_and_session(client, db):
    _signup(client, username="tim", email="tim@test.com")

    resp = client.post(
        "/settings/username",
        data={"username": "newname"},
        follow_redirects=False,
    )

    assert resp.status_code in (302, 303)
    assert "/settings" in resp.headers["Location"]

    with client.session_transaction() as sess:
        user_id = sess["user_id"]
        assert sess["username"] == "newname"

    row = db.getUserInfo(user_id)
    assert row["username"] == "newname"


def test_settings_email_updates_db(client, db):
    _signup(client, username="tim", email="tim@test.com")

    resp = client.post(
        "/settings/email",
        data={"email": "new@test.com"},
        follow_redirects=False,
    )

    assert resp.status_code in (302, 303)
    assert "/settings" in resp.headers["Location"]

    with client.session_transaction() as sess:
        user_id = sess["user_id"]

    row = db.getUserInfo(user_id)
    assert row["email"] == "new@test.com"


def test_settings_password_updates_hash(client, db):
    _signup(client, username="tim", email="tim@test.com")

    with client.session_transaction() as sess:
        user_id = sess["user_id"]

    before = db.get_user_by_email("tim@test.com")
    old_hash = before["password_hash"]

    resp = client.post(
        "/settings/password",
        data={"password": "newpass123"},
        follow_redirects=False,
    )

    assert resp.status_code in (302, 303)
    assert "/settings" in resp.headers["Location"]

    after = db.get_user_by_email("tim@test.com")
    assert after["password_hash"] != old_hash
    assert check_password_hash(after["password_hash"], "newpass123")
    assert int(after["id"]) == int(user_id)
