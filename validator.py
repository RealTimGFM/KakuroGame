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

    def locateErrorInput(self):
        return [self.position]

    def _is_playable(self, idx: int) -> bool:
        return self.pd["mask"][idx] == "0"

    def _row_col(self, idx: int):
        w = self.pd["w"]
        return idx // w, idx % w

    def _index(self, row: int, col: int) -> int:
        return row * self.pd["w"] + col

    def _get_trial_board(self):
        trial = dict(self.board)
        key = str(self.position)
        if self.value == "":
            trial.pop(key, None)
        else:
            trial[key] = self.value
        return trial

    def _get_run_right(self, idx: int):
        row, col = self._row_col(idx)
        cur_col = col - 1
        clue_idx = None

        while cur_col >= 0:
            test_idx = self._index(row, cur_col)
            if self._is_playable(test_idx):
                cur_col -= 1
                continue
            clue_idx = test_idx
            break

        if clue_idx is None:
            return None, []

        clue_tok = self.pd["clues"][clue_idx]
        if clue_tok == ".":
            return None, []

        right_total = int(clue_tok.split("/")[1])
        if right_total <= 0:
            return None, []

        cells = []
        cur_col = self._row_col(clue_idx)[1] + 1
        while cur_col < self.pd["w"]:
            test_idx = self._index(row, cur_col)
            if not self._is_playable(test_idx):
                break
            cells.append(test_idx)
            cur_col += 1

        return right_total, cells

    def _get_run_down(self, idx: int):
        row, col = self._row_col(idx)
        cur_row = row - 1
        clue_idx = None

        while cur_row >= 0:
            test_idx = self._index(cur_row, col)
            if self._is_playable(test_idx):
                cur_row -= 1
                continue
            clue_idx = test_idx
            break

        if clue_idx is None:
            return None, []

        clue_tok = self.pd["clues"][clue_idx]
        if clue_tok == ".":
            return None, []

        down_total = int(clue_tok.split("/")[0])
        if down_total <= 0:
            return None, []

        cells = []
        cur_row = self._row_col(clue_idx)[0] + 1
        while cur_row < self.pd["h"]:
            test_idx = self._index(cur_row, col)
            if not self._is_playable(test_idx):
                break
            cells.append(test_idx)
            cur_row += 1

        return down_total, cells

    def _check_run(self, total, cells, board):
        if total is None or not cells:
            return True

        values = []
        for idx in cells:
            raw = board.get(str(idx), "")
            if raw in (None, "", "."):
                values.append("")
            else:
                values.append(str(raw))

        filled = [int(v) for v in values if v != ""]
        if len(filled) != len(set(filled)):
            return False

        current_sum = sum(filled)
        if "" in values:
            return current_sum < total
        return current_sum == total

    def checkInput(self):
        if not self._is_playable(self.position):
            return False

        if self.value != "" and self.value not in {"1", "2", "3", "4", "5", "6", "7", "8", "9"}:
            return False

        trial_board = self._get_trial_board()

        right_total, right_cells = self._get_run_right(self.position)
        if not self._check_run(right_total, right_cells, trial_board):
            return False

        down_total, down_cells = self._get_run_down(self.position)
        if not self._check_run(down_total, down_cells, trial_board):
            return False

        return True