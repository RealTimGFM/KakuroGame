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

    def checkValid(self, kind: str, value: str) -> bool:
        uid = session.get("user_id")
        if not isinstance(uid, int):
            self.showFailMsg("You must be logged in.")
            return False

        txt = (value or "").strip()

        if kind == "un":
            if not txt:
                self.showFailMsg("Username is required.")
                return False

            if len(txt) < 3:
                self.showFailMsg("Username must be at least 3 characters.")
                return False

            row = self.db.get_user_by_username(txt)
            if row and int(row["id"]) != uid:
                self.showFailMsg("Username already taken.")
                return False

            return True

        if kind == "em":
            email = txt.lower()
            if not email:
                self.showFailMsg("Email is required.")
                return False

            is_legit = re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email) is not None
            if not is_legit:
                self.showFailMsg("Please enter a valid email.")
                return False

            row = self.db.get_user_by_email(email)
            if row and int(row["id"]) != uid:
                self.showFailMsg("Email already registered.")
                return False

            return True

        if kind == "pass":
            if not txt:
                self.showFailMsg("Password is required.")
                return False

            if len(txt) < 6:
                self.showFailMsg("Password must be at least 6 characters.")
                return False

            return True

        self.showFailMsg("Invalid validation type.")
        return False

    def setUsername(self, username: str):
        session["username"] = (username or "").strip()

    def setEmail(self, email: str):
        return (email or "").strip().lower()

    def setHashPass(self, password: str):
        return generate_password_hash(password or "", method="pbkdf2:sha256")

    def changeUsername(self, username: str) -> bool:
        if not self.checkValid("un", username):
            return False

        uid = session.get("user_id")
        new_username = (username or "").strip()

        self.setUsername(new_username)
        self.db.update_username(uid, new_username)
        self.showOkMsg("Username updated successfully.")
        return True

    def changeEmail(self, email: str) -> bool:
        if not self.checkValid("em", email):
            return False

        uid = session.get("user_id")
        new_email = self.setEmail(email)

        self.db.update_email(uid, new_email)
        self.showOkMsg("Email updated successfully.")
        return True

    def changePass(self, password: str) -> bool:
        if not self.checkValid("pass", password):
            return False

        uid = session.get("user_id")
        new_hash = self.setHashPass(password)

        self.db.update_password_hash(uid, new_hash)
        self.showOkMsg("Password updated successfully.")
        return True

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