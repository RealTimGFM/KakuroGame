# tests/test_puzzle_catalog_validation.py
# What it does: Validates every puzzle inside puzzles_import.json using both
# basic importer rules and Kakuro math rules.
# Expected outcome: If any puzzle is broken, this test fails and prints the
# version number plus the reason, so you can fix the bad puzzles quickly.

import json
from pathlib import Path

from puzzle_importer import tokenize_row, validate_puzzle_obj


CATALOG_PATH = Path(__file__).resolve().parents[1] / "puzzles_import.json"


def _load_catalog():
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        root = json.load(f)

    puzzles = root.get("puzzles", [])
    assert isinstance(puzzles, list), "root.puzzles must be an array"
    return puzzles


def _parse_grids(puz):
    w = puz["w"]
    h = puz["h"]

    p_grid = []
    s_grid = []

    for r in range(h):
        p_tokens = tokenize_row(puz["p"][r], w)
        s_tokens = tokenize_row(puz["s"][r], w)

        # Basic validator already checks these, but keep this safe here too.
        if p_tokens is None:
            return None, None
        if s_tokens is None:
            return None, None

        p_grid.append(p_tokens)
        s_grid.append(s_tokens)

    return p_grid, s_grid


def _deep_validate_puzzle(puz):
    ok, err = validate_puzzle_obj(puz)
    if not ok:
        return False, err, []

    w = puz["w"]
    h = puz["h"]
    p_grid, s_grid = _parse_grids(puz)

    if p_grid is None or s_grid is None:
        return False, "row token parsing failed", []

    warnings = []

    def collect_run_right(r, c):
        cells = []
        cc = c + 1
        while cc < w and p_grid[r][cc] == "." and s_grid[r][cc] != ".":
            cells.append((r, cc))
            cc += 1
        return cells

    def collect_run_down(r, c):
        cells = []
        rr = r + 1
        while rr < h and p_grid[rr][c] == "." and s_grid[rr][c] != ".":
            cells.append((rr, c))
            rr += 1
        return cells

    def digits_for(cells):
        return [int(s_grid[rr][cc]) for rr, cc in cells]

    # Check every clue cell and verify its run math.
    for r in range(h):
        for c in range(w):
            pt = p_grid[r][c]
            st = s_grid[r][c]

            if pt == ".":
                continue

            if st != ".":
                return False, f"clue cell must have '.' in solution at ({r},{c})", warnings

            down_sum, right_sum = map(int, pt.split("/"))

            if right_sum > 0:
                cells = collect_run_right(r, c)
                if not cells:
                    return False, f"clue points to missing run at ({r},{c}) across", warnings

                vals = digits_for(cells)

                if len(cells) == 1:
                    warnings.append(f"v{puz['v']}: 1-cell across run at ({r},{c})")

                if len(set(vals)) != len(vals):
                    return False, f"repeated digits in across run from ({r},{c}): {vals}", warnings

                if sum(vals) != right_sum:
                    return False, (
                        f"sum mismatch in across run from ({r},{c}): "
                        f"expected {right_sum}, got {sum(vals)} from {vals}"
                    ), warnings
            else:
                if c + 1 < w and p_grid[r][c + 1] == "." and s_grid[r][c + 1] != ".":
                    return False, f"across 0 but has white cells to the right at ({r},{c})", warnings

            if down_sum > 0:
                cells = collect_run_down(r, c)
                if not cells:
                    return False, f"clue points to missing run at ({r},{c}) down", warnings

                vals = digits_for(cells)

                if len(cells) == 1:
                    warnings.append(f"v{puz['v']}: 1-cell down run at ({r},{c})")

                if len(set(vals)) != len(vals):
                    return False, f"repeated digits in down run from ({r},{c}): {vals}", warnings

                if sum(vals) != down_sum:
                    return False, (
                        f"sum mismatch in down run from ({r},{c}): "
                        f"expected {down_sum}, got {sum(vals)} from {vals}"
                    ), warnings
            else:
                if r + 1 < h and p_grid[r + 1][c] == "." and s_grid[r + 1][c] != ".":
                    return False, f"down 0 but has white cells below at ({r},{c})", warnings

    # Check every white cell with a digit.
    # In Kakuro, each playable cell should belong to one across run and one down run.
    for r in range(h):
        for c in range(w):
            if p_grid[r][c] != "." or s_grid[r][c] == ".":
                continue

            # Find nearest clue on the left.
            left_has_across = False
            cc = c - 1
            while cc >= 0 and p_grid[r][cc] == ".":
                cc -= 1
            if cc >= 0 and p_grid[r][cc] != ".":
                down_sum, right_sum = map(int, p_grid[r][cc].split("/"))
                if right_sum > 0:
                    left_has_across = True

            # Find nearest clue above.
            up_has_down = False
            rr = r - 1
            while rr >= 0 and p_grid[rr][c] == ".":
                rr -= 1
            if rr >= 0 and p_grid[rr][c] != ".":
                down_sum, right_sum = map(int, p_grid[rr][c].split("/"))
                if down_sum > 0:
                    up_has_down = True

            if not left_has_across and not up_has_down:
                return False, f"uncovered white cell at ({r},{c})", warnings
            if not left_has_across:
                return False, f"white cell missing across clue at ({r},{c})", warnings
            if not up_has_down:
                return False, f"white cell missing down clue at ({r},{c})", warnings

    return True, "", warnings


def test_puzzles_import_json_has_unique_versions():
    puzzles = _load_catalog()
    seen = set()
    dupes = []

    for puz in puzzles:
        v = puz.get("v")
        if v in seen:
            dupes.append(v)
        seen.add(v)

    assert not dupes, f"Duplicate puzzle version(s) found: {dupes}"


def test_puzzles_import_json_has_no_broken_puzzles():
    puzzles = _load_catalog()

    broken = []
    warning_only = []

    for puz in puzzles:
        ok, err, warnings = _deep_validate_puzzle(puz)
        v = puz.get("v", "?")

        if not ok:
            broken.append(f"v{v}: {err}")
        elif warnings:
            warning_only.extend(warnings)

    warning_text = ""
    if warning_only:
        warning_text = "\n\nNon-failing warnings:\n" + "\n".join(f"- {msg}" for msg in warning_only)

    assert not broken, (
        "Broken puzzles found in puzzles_import.json:\n"
        + "\n".join(f"- {msg}" for msg in broken)
        + warning_text
    )
