# What it does: Tests fillCells flow and invalid input highlight behavior.
# Expected outcome: Valid input saves the value; invalid text is still saved and all invalid cells are highlighted.
from tests.conftest import insert_puzzle_with_solution


def _login_and_seed(client, seed):
    client.post("/signup", data={
        "username": "tim",
        "email": "tim@test.com",
        "password": "123456",
        "confirm_password": "123456",
    })
    client.post("/seed", data={"seed": seed})


def test_fill_cells_valid_flow_updates_board(client, db, seed_code):
    insert_puzzle_with_solution(db, seed_code)
    _login_and_seed(client, seed_code)

    r = client.post("/seed/fill", json={"position": 4, "value": "2"})
    assert r.status_code == 200
    j = r.get_json()
    assert j["ok"] is True
    assert j["value"] == "2"
    assert j["invalid_positions"] == []

    with client.session_transaction() as sess:
        assert sess["seeded_puzzle_board"]["4"] == "2"


def test_fill_cells_invalid_text_is_saved_and_highlighted(client, db, seed_code):
    insert_puzzle_with_solution(db, seed_code)
    _login_and_seed(client, seed_code)

    r = client.post("/seed/fill", json={"position": 4, "value": "a"})
    assert r.status_code == 200
    j = r.get_json()
    assert j["ok"] is True
    assert j["value"] == "a"
    assert j["invalid_positions"] == [4]

    with client.session_transaction() as sess:
        assert sess["seeded_puzzle_board"]["4"] == "a"
        assert sess["seeded_puzzle_invalid_positions"] == [4]


def test_fill_cells_highlights_all_invalid_cells(client, db, seed_code):
    insert_puzzle_with_solution(db, seed_code)
    _login_and_seed(client, seed_code)

    client.post("/seed/fill", json={"position": 4, "value": "a"})
    r = client.post("/seed/fill", json={"position": 5, "value": "0"})
    assert r.status_code == 200
    j = r.get_json()
    assert j["ok"] is True
    assert j["invalid_positions"] == [4, 5]

    with client.session_transaction() as sess:
        assert sess["seeded_puzzle_board"]["4"] == "a"
        assert sess["seeded_puzzle_board"]["5"] == "0"
        assert sess["seeded_puzzle_invalid_positions"] == [4, 5]


def test_fill_cells_wrong_valid_digit_is_not_highlighted(client, db, seed_code):
    insert_puzzle_with_solution(db, seed_code)
    _login_and_seed(client, seed_code)

    r = client.post("/seed/fill", json={"position": 4, "value": "9"})
    assert r.status_code == 200
    j = r.get_json()
    assert j["ok"] is True
    assert j["value"] == "9"
    assert j["invalid_positions"] == []

    with client.session_transaction() as sess:
        assert sess["seeded_puzzle_board"]["4"] == "9"
        assert sess["seeded_puzzle_invalid_positions"] == []