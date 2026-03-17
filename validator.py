import json


class Validator:
    def __init__(self, puzzle_data_str: str, position: int, value: str, board: dict):
        self.pd = json.loads(puzzle_data_str)
        self.position = int(position)
        self.value = "" if value is None else str(value).strip()
        self.board = dict(board or {})

    @classmethod
    def create(cls, puzzle_data_str: str, position: int, value: str, board: dict):
        return cls(puzzle_data_str, position, value, board)

    def checkInput(self):
        if self.position < 0:
            return False

        if self.position >= len(self.pd["mask"]):
            return False

        if self.pd["mask"][self.position] != "0":
            return False

        if self.value == "":
            return True

        return self.value in {"1", "2", "3", "4", "5", "6", "7", "8", "9"}

    def locateErrorInput(self):
        trial_board = dict(self.board)
        key = str(self.position)

        if self.value == "":
            trial_board.pop(key, None)
        else:
            trial_board[key] = self.value

        invalid_positions = []

        total = self.pd["w"] * self.pd["h"]
        mask = self.pd["mask"]

        for i in range(total):
            if mask[i] != "0":
                continue

            raw = trial_board.get(str(i), "")
            txt = "" if raw is None else str(raw).strip()

            if txt == "":
                continue

            if txt not in {"1", "2", "3", "4", "5", "6", "7", "8", "9"}:
                invalid_positions.append(i)

        return invalid_positions