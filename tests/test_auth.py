# What it does: Tests signup and login rules (successful signup/login, bad email rejected, wrong password rejected).
# Expected outcome: Success redirects to dashboard and sets session, bad inputs show an error message on the page.
def test_signup_then_login_success(client, db):
    resp = client.post("/signup", data={
        "username": "tim",
        "email": "tim@test.com",
        "password": "123456",
        "confirm_password": "123456",
    }, follow_redirects=False)
    assert resp.status_code in (302, 303)

    client.get("/logout")

    resp2 = client.post("/login", data={
        "email": "tim@test.com",
        "password": "123456",
    }, follow_redirects=False)
    assert resp2.status_code in (302, 303)

    with client.session_transaction() as sess:
        assert "user_id" in sess
        assert sess["username"] == "tim"


def test_signup_rejects_bad_email(client):
    resp = client.post("/signup", data={
        "username": "u1",
        "email": "not-an-email",
        "password": "123456",
        "confirm_password": "123456",
    }, follow_redirects=True)

    assert b"valid email" in resp.data.lower()


def test_login_rejects_wrong_password(client):
    client.post("/signup", data={
        "username": "u2",
        "email": "u2@test.com",
        "password": "123456",
        "confirm_password": "123456",
    })
    client.get("/logout")

    resp = client.post("/login", data={
        "email": "u2@test.com",
        "password": "WRONG",
    }, follow_redirects=True)

    assert b"invalid email or password" in resp.data.lower()