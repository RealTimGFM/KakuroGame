import re
from typing import Optional, Tuple
from flask import flash, session
from werkzeug.security import generate_password_hash, check_password_hash


class RegisteredUser:
    def __init__(self, db):
        self.db = db

    def showOkMsg(self, msg: str):
        flash(msg, "success")

    def showFailMsg(self, msg: str):
        flash(msg, "error")

    def checkEmail(self, email: str) -> Tuple[bool, bool]:
        e = (email or "").strip().lower()
        is_legit = re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", e) is not None
        exists = self.db.get_user_by_email(e) is not None
        return (is_legit, exists)

    def checkCred(self, email: str, password: str) -> bool:
        e = (email or "").strip().lower()
        if not e or not password:
            return False
        user = self.db.get_user_by_email(e)
        if not user:
            return False
        return check_password_hash(user["password_hash"], password)

    # Authenticate an existing user and populate the session.
    # Removes is_guest so the session is no longer treated as a guest.
    def login(self, email: str, password: str) -> bool:
        e = (email or "").strip().lower()
        user = self.db.get_user_by_email(e)

        if not user or not check_password_hash(user["password_hash"], password or ""):
            self.showFailMsg("Invalid email or password.")
            return False

        session["user_id"] = user["id"]
        session["username"] = user["username"]
        session.pop("is_guest", None)
        self.showOkMsg("Login successful!")
        return True

    # Create a new account and populate the session.
    # Removes is_guest so the session is no longer treated as a guest.
    def createAccount(self, username: str, email: str, password: str, confirm_password: str) -> Optional[int]:
        username = (username or "").strip()
        email = (email or "").strip().lower()
        password = password or ""
        confirm_password = confirm_password or ""

        if not username or not email or not password or not confirm_password:
            self.showFailMsg("All fields are required.")
            return None

        if password != confirm_password:
            self.showFailMsg("Passwords do not match.")
            return None

        if len(password) < 6:
            self.showFailMsg("Password must be at least 6 characters.")
            return None

        is_legit, email_exists = self.checkEmail(email)
        if not is_legit:
            self.showFailMsg("Please enter a valid email.")
            return None

        if self.db.get_user_by_username(username):
            self.showFailMsg("Username already taken.")
            return None

        if email_exists:
            self.showFailMsg("Email already registered.")
            return None

        hashed = generate_password_hash(password, method="pbkdf2:sha256")
        user_id = self.db.create_user(username, email, hashed)

        session["user_id"] = user_id
        session["username"] = username
        session.pop("is_guest", None)
        self.showOkMsg("Account created successfully!")
        return user_id