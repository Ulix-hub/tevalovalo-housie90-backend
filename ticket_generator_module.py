# ticket_generator_module.py
# Generates a valid Housie90 strip (6 tickets) and validates strips.
# Rules enforced:
# - Each ticket is 3x9
# - Each row has exactly 5 numbers (15 per ticket)
# - Column ranges: [1–9],[10–19],...,[80–90]
# - Across the strip, 1..90 appear exactly once (no duplicates/missing)
# - Per ticket per column: at most 3 numbers
# - Numbers in each column ascend top->bottom (within a ticket)
# - Blanks are 0

import random
from typing import List, Optional, Tuple, Dict, Any
from itertools import combinations

TICKETS_PER_STRIP = 6
ROWS = 3
COLS = 9

COLUMN_RANGES = {
    0: list(range(1, 10)),
    1: list(range(10, 20)),
    2: list(range(20, 30)),
    3: list(range(30, 40)),
    4: list(range(40, 50)),
    5: list(range(50, 60)),
    6: list(range(60, 70)),
    7: list(range(70, 80)),
    8: list(range(80, 91)),
}
# Totals across a 6-ticket strip: [9,10,10,10,10,10,10,10,11]
COLUMN_TOTALS = [len(COLUMN_RANGES[c]) for c in range(COLS)]


def generate_full_strip() -> List[List[List[Optional[int]]]]:
    """Return a list of 6 tickets; each ticket is a 3x9 list of ints (0 = blank)."""
    for _ in range(200):
        try:
            counts = _allocate_col_counts()
            layouts = [_assign_rows_for_ticket(counts[t]) for t in range(TICKETS_PER_STRIP)]
            strip = _fill_numbers(layouts)
            # Defensive: ensure validity before returning
            rep = validate_strip(strip)
            if rep["ok"]:
                return strip
        except Exception:
            continue
    raise ValueError("Failed to generate a valid housie strip after many attempts")


# ---------- Validation exposed to app.py ----------
def validate_strip(strip: List[List[List[Optional[int]]]]) -> Dict[str, Any]:
    """
    Validate a 6-ticket strip against Housie rules.
    Returns a report dict: {ok: bool, errors: [..], strip_col_totals: [...], missing: [...], duplicates: [...]}.
    """
    errors: List[str] = []

    if not isinstance(strip, list) or len(strip) != TICKETS_PER_STRIP:
        errors.append(f"strip must have {TICKETS_PER_STRIP} tickets")

    used = []
    strip_col_totals = [0]*COLS

    for ti, ticket in enumerate(strip or []):
        # shape
        if not isinstance(ticket, list) or len(ticket) != ROWS:
            errors.append(f"ticket {ti}: must have {ROWS} rows")
            continue

        # each row exactly 5
        for r in range(ROWS):
            row = ticket[r]
            if not isinstance(row, list) or len(row) != COLS:
                errors.append(f"ticket {ti} row {r}: must have {COLS} cols")
                continue
            filled = sum(1 for v in row if v not in (0, None))
            if filled != 5:
                errors.append(f"ticket {ti} row {r}: has {filled} numbers (expected 5)")

        # per-column checks (<=3, ascending, range, and strip totals)
        for c in range(COLS):
            col_vals = [ticket[r][c] for r in range(ROWS) if ticket[r][c] not in (0, None)]
            strip_col_totals[c] += len(col_vals)

            # <= 3
            if len(col_vals) > 3:
                errors.append(f"ticket {ti} col {c}: >3 numbers")

            # ascending inside column
            if col_vals != sorted(col_vals):
                errors.append(f"ticket {ti} col {c}: not ascending {col_vals}")

            # range check
            lo, hi = COLUMN_RANGES[c][0], COLUMN_RANGES[c][-1]
            for v in col_vals:
                if not (lo <= v <= hi):
                    errors.append(f"ticket {ti} col {c}: value {v} out of range {lo}-{hi}")

            used.extend(col_vals)

    # Column totals across strip
    if strip_col_totals != COLUMN_TOTALS:
        errors.append(
            f"strip col totals {strip_col_totals} != expected {COLUMN_TOTALS}"
        )

    # Uniqueness across strip: exactly numbers 1..90 once
    want = set(range(1, 91))
    got = set(used)
    missing = sorted(list(want - got))
    extra = sorted(list(got - want))

    if missing:
        errors.append(f"missing {len(missing)} numbers from 1..90")
    if extra:
        errors.append(f"found {len(extra)} numbers outside 1..90")

    # dup check
    counts: Dict[int, int] = {}
    for v in used:
        counts[v] = counts.get(v, 0) + 1
    duplicates = sorted([v for v, n in counts.items() if n > 1])
    if duplicates:
        errors.append(f"duplicates present: {duplicates[:10]}{'...' if len(duplicates) > 10 else ''}")

    return {
        "ok": len(errors) == 0 and not missing and not duplicates and not extra and strip_col_totals == COLUMN_TOTALS,
        "errors": errors,
        "strip_col_totals": strip_col_totals,
        "missing": missing,
        "duplicates": duplicates,
        "extra": extra,
    }


# ------------ A) counts per ticket/column ------------
def _allocate_col_counts() -> List[List[int]]:
    counts = [[0]*COLS for _ in range(TICKETS_PER_STRIP)]
    ticket_sums = [0]*TICKETS_PER_STRIP

    col_order = list(range(COLS))
    col_order.sort(key=lambda c: COLUMN_TOTALS[c], reverse=True)

    def dfs(ci: int) -> bool:
        if ci == COLS:
            return all(s == 15 for s in ticket_sums)

        c = col_order[ci]
        need = COLUMN_TOTALS[c]
        ticket_order = list(range(TICKETS_PER_STRIP))
        random.shuffle(ticket_order)
        col_counts = [0] * TICKETS_PER_STRIP

        def place_for_ticket(i: int, remaining: int) -> bool:
            if i == TICKETS_PER_STRIP:
                if remaining != 0:
                    return False
                remaining_cols = COLS - (ci + 1)
                for t in range(TICKETS_PER_STRIP):
                    s2 = ticket_sums[t] + col_counts[t]
                    if s2 > 15:
                        return False
                    if 15 - s2 > 3 * remaining_cols:
                        return False
                for t in range(TICKETS_PER_STRIP):
                    counts[t][c] = col_counts[t]
                    ticket_sums[t] += col_counts[t]
                ok = dfs(ci + 1)
                if not ok:
                    for t in range(TICKETS_PER_STRIP):
                        ticket_sums[t] -= col_counts[t]
                        counts[t][c] = 0
                return ok

            t = ticket_order[i]
            remaining_cols = COLS - (ci + 1)
            need_ticket = 15 - ticket_sums[t]
            min_x = max(0, need_ticket - 3 * remaining_cols)
            max_x = min(3, remaining, need_ticket)
            if min_x > max_x:
                return False
            choices = list(range(min_x, max_x + 1))
            random.shuffle(choices)
            choices.sort(reverse=True)
            for x in choices:
                col_counts[t] = x
                if place_for_ticket(i + 1, remaining - x):
                    return True
            col_counts[t] = 0
            return False

        return place_for_ticket(0, need)

    if not dfs(0):
        raise ValueError("count allocation failed")
    return counts


# ------------ B) rows inside each ticket ------------
def _assign_rows_for_ticket(col_counts: List[int]) -> List[List[int]]:
    layout = [[0]*COLS for _ in range(ROWS)]
    rows_left = [5, 5, 5]
    cols_with_counts = [c for c in range(COLS) if col_counts[c] > 0]
    cols_with_counts.sort(key=lambda c: col_counts[c], reverse=True)
    total_to_place = sum(col_counts)

    def feasible_after(i: int) -> bool:
        remain_cols = len(cols_with_counts) - i
        for r in range(ROWS):
            if rows_left[r] > remain_cols:
                return False
        return True

    def dfs(i: int, placed: int) -> bool:
        if i == len(cols_with_counts):
            return rows_left == [0, 0, 0] and placed == total_to_place
        if not feasible_after(i):
            return False
        c = cols_with_counts[i]
        k = col_counts[c]

        def apply_rows(rows: Tuple[int, ...], on: bool):
            d = 1 if on else -1
            for r in rows:
                layout[r][c] = 1 if on else 0
                rows_left[r] -= d

        if k == 3:
            if all(rows_left[r] > 0 for r in range(ROWS)):
                apply_rows((0, 1, 2), True)
                if dfs(i + 1, placed + 3):
                    return True
                apply_rows((0, 1, 2), False)
            return False

        candidates = [r for r in range(ROWS) if rows_left[r] > 0]
        if k == 2:
            for pair in combinations(candidates, 2):
                apply_rows(pair, True)
                if dfs(i + 1, placed + 2):
                    return True
                apply_rows(pair, False)
            return False

        if k == 1:
            candidates.sort(key=lambda r: rows_left[r], reverse=True)
            for r in candidates:
                apply_rows((r,), True)
                if dfs(i + 1, placed + 1):
                    return True
                apply_rows((r,), False)
            return False

        return dfs(i + 1, placed)

    if not dfs(0, 0):
        raise ValueError("row assignment failed")
    return layout


# ------------ C) fill numbers into the layouts ------------
def _fill_numbers(layouts: List[List[List[int]]]) -> List[List[List[int]]]:
    pools = {c: COLUMN_RANGES[c][:] for c in range(COLS)}
    for c in range(COLS):
        random.shuffle(pools[c])

    strip = [[[0]*COLS for _ in range(ROWS)] for _ in range(TICKETS_PER_STRIP)]

    for c in range(COLS):
        pool = pools[c]
        idx = 0

        per_ticket_rows = []
        for t in range(TICKETS_PER_STRIP):
            rows_here = [r for r in range(ROWS) if layouts[t][r][c] == 1]
            per_ticket_rows.append((t, rows_here))
        random.shuffle(per_ticket_rows)

        # place numbers; keep ascending inside each ticket column
        for t, rows_here in per_ticket_rows:
            k = len(rows_here)
            if k == 0:
                continue
            chosen = pool[idx: idx + k]
            idx += k
            chosen.sort()
            for rr, val in zip(sorted(rows_here), chosen):
                strip[t][rr][c] = val

        if idx != COLUMN_TOTALS[c]:
            raise ValueError("column fill mismatch")

    return strip
