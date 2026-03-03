import json
import os
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple


KAKURO_NAMESPACE = uuid.UUID("f3f7d6a3-7b3b-4f3a-a9ad-7d7d39e3f1cb")


# Read the import JSON file and return the root object.
# If the file does not exist or cannot be read, return None.
def load_import_json(path: str) -> Optional[Dict[str, Any]]:
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"import error: failed to read {path}: {e}")
        return None


# Make a stable UUID seed from v.
# Same v -> same seed every time, using uuid5(namespace, "kakuro:" + str(v)).
def derive_seed_from_v(v: Any) -> str:
    name = "kakuro:" + str(v)
    return str(uuid.uuid5(KAKURO_NAMESPACE, name))


# Split one row string into tokens and make sure it has exactly w tokens.
# Returns the list of tokens, or None if the count is wrong.
def tokenize_row(row: str, w: int) -> Optional[List[str]]:
    tokens = str(row).strip().split()
    if len(tokens) != w:
        return None
    return tokens


# Check if a layout token is valid.
# Valid layout token is "." OR "A/B" where A and B are non-negative integers.
def is_layout_token(tok: str) -> bool:
    if tok == ".":
        return True
    return re.fullmatch(r"\d+/\d+", tok) is not None


# Check if a solution token is valid.
# Valid solution token is "." OR a single digit from 1 to 9.
def is_solution_token(tok: str) -> bool:
    if tok == ".":
        return True
    return re.fullmatch(r"[1-9]", tok) is not None


# Validate one puzzle object (fields, sizes, token rules).
# Returns (True, "") if ok, or (False, "error message") if not ok.
#
# How it works (simple steps):
# 1) Check required fields exist: v,w,h,stage,level,p,s.
# 2) Check stage is one of the allowed values and level is 1..5.
# 3) Check w/h are positive integers and p/s are arrays with exactly h rows.
# 4) For each row, split into tokens and require exactly w tokens.
# 5) For each cell, validate token formats and enforce:
#    - If p is a clue (A/B), then s must be "." (no digit on clue cells).
def validate_puzzle_obj(puz: Dict[str, Any]) -> Tuple[bool, str]:
    required = ["v", "w", "h", "stage", "level", "p", "s"]
    for k in required:
        if k not in puz:
            return False, f"missing field: {k}"

    w = puz["w"]
    h = puz["h"]
    p = puz["p"]
    s = puz["s"]
    stage = puz["stage"]
    level = puz["level"]

    if stage not in ("Learner", "Intermediate", "Master"):
        return False, "stage must be Learner|Intermediate|Master"

    if not isinstance(level, int) or not (1 <= level <= 5):
        return False, "level must be int 1..5"

    if not isinstance(w, int) or not isinstance(h, int) or w <= 0 or h <= 0:
        return False, "w/h must be positive ints"

    if not isinstance(p, list) or not isinstance(s, list):
        return False, "p and s must be arrays"

    if len(p) != h or len(s) != h:
        return False, "p length and s length must equal h"

    for r in range(h):
        p_tokens = tokenize_row(p[r], w)
        s_tokens = tokenize_row(s[r], w)

        if p_tokens is None:
            return False, f"row {r} in p does not have exactly w tokens"
        if s_tokens is None:
            return False, f"row {r} in s does not have exactly w tokens"

        for c in range(w):
            pt = p_tokens[c]
            st = s_tokens[c]

            if not is_layout_token(pt):
                return False, f"invalid p token at ({r},{c}): {pt}"
            if not is_solution_token(st):
                return False, f"invalid s token at ({r},{c}): {st}"

            if pt != "." and st != ".":
                return False, f"clue cell must have '.' in solution at ({r},{c})"

    return True, ""


# Convert p and s row strings into flat lists (row-major order).
# Example: 6x6 -> lists of length 36.
def flatten_tokens(p_rows: List[str], s_rows: List[str], w: int, h: int) -> Tuple[List[str], List[str]]:
    p_flat: List[str] = []
    s_flat: List[str] = []
    for r in range(h):
        p_flat.extend(tokenize_row(p_rows[r], w) or [])
        s_flat.extend(tokenize_row(s_rows[r], w) or [])
    return p_flat, s_flat


# Build the derived fields from flattened p/s tokens:
# - mask: a single string of 0/1 (0 = playable, 1 = not playable)
# - clues: a list where clue cells keep "A/B" and others are "."
# - digits: a single string with digits (1..9) for playable cells and "." for others

def derive_fields(p_flat: List[str], s_flat: List[str]) -> Tuple[str, List[str], str]:
    mask_bits: List[str] = []
    clues: List[str] = []
    digits_chars: List[str] = []

    n = len(p_flat)
    for i in range(n):
        pt = p_flat[i]
        st = s_flat[i]

        if pt != ".":
            mask_bits.append("1")
            clues.append(pt)
            digits_chars.append(".")
        else:
            clues.append(".")
            if st != ".":
                mask_bits.append("0")
                digits_chars.append(st)
            else:
                mask_bits.append("1")
                digits_chars.append(".")

    return "".join(mask_bits), clues, "".join(digits_chars)


# Build the puzzle_data JSON string (safe for client).
# This includes metadata + clues + mask, but NOT the solution digits.
def build_puzzle_data(v: Any, w: int, h: int, stage: str, level: int, clues: List[str], mask: str) -> str:
    obj = {
        "schema": 1,
        "v": v,
        "w": w,
        "h": h,
        "stage": stage,
        "level": level,
        "clues": clues,
        "mask": mask
    }
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


# Build the solution_data JSON string (digits only).
# This must never be returned by normal puzzle endpoints.
def build_solution_data(v: Any, w: int, h: int, digits: str) -> str:
    obj = {
        "schema": 1,
        "v": v,
        "w": w,
        "h": h,
        "digits": digits
    }
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


# Read puzzles from a JSON file and insert them into the DB.
# It validates input and skips duplicates by v (within the file) and by seed (already in DB).
#
# How it works (simple steps):
# 1) Load the JSON file. If missing/broken, do nothing.
# 2) Read root["puzzles"] and make sure it is a list.
# 3) Track v values in a set (seen_v) to skip repeated v in the same file.
# 4) For each puzzle:
#    - Validate the object (fields + tokens + rules)
#    - Create seed from v
#    - If the seed already exists in DB, skip and print "skip puzzle <v>"
#    - Flatten rows, derive mask/clues/digits
#    - Build puzzle_data and solution_data JSON strings
#    - Insert into DB (puzzle then solution)
def import_puzzles_from_file(db, path: str) -> None:
    root = load_import_json(path)
    if root is None:
        return

    puzzles = root.get("puzzles", [])
    if not isinstance(puzzles, list):
        print("import error: root.puzzles must be an array")
        return

    seen_v = set()

    for puz in puzzles:
        if not isinstance(puz, dict):
            print("import error: puzzle entry must be an object")
            continue

        v = puz.get("v")

        if v in seen_v:
            print(f"skip puzzle {v}")
            continue
        seen_v.add(v)

        ok, err = validate_puzzle_obj(puz)
        if not ok:
            print(f"import error puzzle {v}: {err}")
            continue

        seed = derive_seed_from_v(v)
        if db.get_puzzle_by_seed(seed) is not None:
            print(f"skip puzzle {v}")
            continue

        w = puz["w"]
        h = puz["h"]
        stage = puz["stage"]
        level = puz["level"]
        p_rows = puz["p"]
        s_rows = puz["s"]

        p_flat, s_flat = flatten_tokens(p_rows, s_rows, w, h)
        mask, clues, digits = derive_fields(p_flat, s_flat)

        if len(mask) != w * h:
            print(f"import error puzzle {v}: mask length mismatch")
            continue
        if len(clues) != w * h:
            print(f"import error puzzle {v}: clues length mismatch")
            continue
        if len(digits) != w * h:
            print(f"import error puzzle {v}: digits length mismatch")
            continue

        puzzle_data = build_puzzle_data(v, w, h, stage, level, clues, mask)
        solution_data = build_solution_data(v, w, h, digits)

        try:
            db.insert_puzzle(seed, puzzle_data, stage, level)
            db.insert_puzzle_solution(seed, solution_data)
        except Exception as e:
            print(f"import error puzzle {v}: db insert failed: {e}")
            continue