# What it does: Creates a fresh Flask app + fresh temp SQLite database for every test, and gives a test client.
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pytest
from app import create_app
from database import Database


@pytest.fixture
def app(tmp_path):
    db_file = tmp_path / "test.db"
    app = create_app(db_path=str(db_file), testing=True)
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db(app):
    return Database(db_path=app.config["DB_PATH"])


@pytest.fixture
def seed_code():
    # 6-char seed: lowercase letters + digits
    return "3fu9a4"


def insert_puzzle(db: Database, seed: str, puzzle_data: str = "{}"):
    con = db.get_connection()
    cur = con.cursor()
    cur.execute(
        "INSERT INTO puzzles (seed, puzzle_data, difficulty, campaign_level) VALUES (?, ?, ?, ?)",
        (seed, puzzle_data, "easy", 1)
    )
    con.commit()
    con.close()

@pytest.fixture
def seed_uuid(seed_code):
    # Alias for older test name; seed must be 6 chars [0-9a-z]
    return seed_code