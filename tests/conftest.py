import json
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
    return "3fu9a4"


def make_puzzle_data():
    return json.dumps({
        "schema": 1,
        "v": 1,
        "w": 3,
        "h": 3,
        "stage": "Learner",
        "level": 1,
        "clues": [".", "11/0", "3/0", "0/3", ".", ".", "0/11", ".", "."],
        "mask": "111100100"
    }, separators=(",", ":"))


def make_solution_data():
    return json.dumps({
        "schema": 1,
        "v": 1,
        "w": 3,
        "h": 3,
        "digits": "....21.92"
    }, separators=(",", ":"))


def insert_puzzle(db: Database, seed: str, puzzle_data: str = None, difficulty: str = "easy", campaign_level: int = 1):
    if puzzle_data is None:
        puzzle_data = make_puzzle_data()
    con = db.get_connection()
    cur = con.cursor()
    cur.execute(
        "INSERT INTO puzzles (seed, puzzle_data, difficulty, campaign_level) VALUES (?, ?, ?, ?)",
        (seed, puzzle_data, difficulty, campaign_level)
    )
    con.commit()
    con.close()


def insert_puzzle_with_solution(
    db: Database,
    seed: str,
    puzzle_data: str = None,
    solution_data: str = None,
    difficulty: str = "easy",
    campaign_level: int = 1,
):
    if puzzle_data is None:
        puzzle_data = make_puzzle_data()
    if solution_data is None:
        solution_data = make_solution_data()

    insert_puzzle(db, seed, puzzle_data, difficulty=difficulty, campaign_level=campaign_level)
    con = db.get_connection()
    cur = con.cursor()
    cur.execute(
        "INSERT INTO puzzle_solutions (seed, solution_data) VALUES (?, ?)",
        (seed, solution_data)
    )
    con.commit()
    con.close()


@pytest.fixture
def seed_uuid(seed_code):
    return seed_code