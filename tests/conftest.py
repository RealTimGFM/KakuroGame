import json
import sys
import shutil
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from app import create_app
from database import Database


@pytest.fixture
def workspace_tmp_dir():
    base = Path(__file__).resolve().parent / "_tmp"
    base.mkdir(exist_ok=True)
    path = base / f"run_{uuid.uuid4().hex}"
    path.mkdir()
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def app(workspace_tmp_dir):
    db_file = workspace_tmp_dir / "test.db"
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


def insert_puzzle(db: Database, seed: str, puzzle_data: str = None):
    if puzzle_data is None:
        puzzle_data = make_puzzle_data()
    con = db.get_connection()
    cur = con.cursor()
    cur.execute(
        "INSERT INTO puzzles (seed, puzzle_data, difficulty, campaign_level) VALUES (?, ?, ?, ?)",
        (seed, puzzle_data, "easy", 1)
    )
    con.commit()
    con.close()


def insert_puzzle_with_solution(db: Database, seed: str, puzzle_data: str = None, solution_data: str = None):
    if puzzle_data is None:
        puzzle_data = make_puzzle_data()
    if solution_data is None:
        solution_data = make_solution_data()

    insert_puzzle(db, seed, puzzle_data)
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
