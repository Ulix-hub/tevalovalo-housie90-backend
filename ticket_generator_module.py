# ticket_generator_module.py
# Generates a valid Housie90 strip (6 tickets) with guarantees:
# - Each ticket: 3x9, each row has exactly 5 numbers (15 total)
# - Column ranges: [1–9], [10–19], ..., [80–90]
# - Across the strip, every number 1..90 appears exactly once
# - Per ticket per column <= 3; numbers in each column ascend top→bottom
# - Blanks are 0

import random
from typing import List, Optional, Tuple
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
# Totals across a 6-ticket strip → [9,10,10,10,10,10,10,10,11]
COLUMN_TOTALS = [len(COLUMN_RANGES[c]) for c in range(COLS)]

def generate_full_strip() -> List[List[List[Optional[int]]]]:
    for _ in range(200):
        try:
            counts = _allocate_col_counts()                         # A) counts per ticket/column (0..3)
            layouts = [_assign_rows_for_ticket(counts[t])           # B) rows per ticket to get 5 per row
                       for t in range(TICKETS_PER_STRIP)]
            strip = _fill_numbers(layouts)                          # C) place actual numbers, ascending
            _verify_strip(strip)                                    # defensive
            return strip
        except Exception:
            continue
    raise ValueError("Failed to generate a valid housie strip after many attempts")

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
                if remaining != 0: return False
                remaining_cols = COLS - (ci + 1)
                for t in range(TICKETS_PER_STRIP):
                    s2 = ticket_sums[t] + col_counts[t]
                    if s2 > 15: return False
                    if 15 - s2 > 3 * remaining_cols: return False
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
            if min_x > max_x: return False
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
        if not feasible_after(i): return False
        c = cols_with_counts[i]
        k = col_counts[c]

        def apply_rows(rows: Tuple[int, ...], on: bool):
            d = 1 if on else -1
            for r in rows:
                layout[r][c] = 1 if on else 0
                rows_left[r] -= d

        if k == 3:
            if all(rows_left[r] > 0 for r in range(ROWS)):
                apply_rows((0,1,2), True)
                if dfs(i+1, placed+3): return True
                apply_rows((0,1,2), False)
            return False

        candidates = [r for r in range(ROWS) if rows_left[r] > 0]
        if k == 2:
            for pair in combinations(candidates, 2):
                apply_rows(pair, True)
                if dfs(i+1, placed+2): return True
                apply_rows(pair, False)
            return False

        if k == 1:
            candidates.sort(key=lambda r: rows_left[r], reverse=True)
            for r in candidates:
                apply_rows((r,), True)
                if dfs(i+1, placed+1): return True
                apply_rows((r,), False)
            return False

        return dfs(i+1, placed)

    if not dfs(0, 0):
        raise ValueError("row assignment failed")
    return layout

# ------------ C) fill numbers into layouts ------------
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

        for t, rows_here in per_ticket_rows:
            k = len(rows_here)
            if k == 0: continue
            chosen = pool[idx: idx + k]
            idx += k
            chosen.sort()  # ensure ascending inside the column
            for rr, val in zip(sorted(rows_here), chosen):
                strip[t][rr][c] = val

        if idx != COLUMN_TOTALS[c]:
            raise ValueError("column fill mismatch")

    return strip

# ------------ validation (defensive) ------------
def _verify_strip(strip: List[List[List[int]]]) -> None:
    assert len(strip) == TICKETS_PER_STRIP
    used = set()
    for t in range(TICKETS_PER_STRIP):
        ticket = strip[t]
        assert len(ticket) == ROWS
        for r in range(ROWS):
            row = ticket[r]
            assert len(row) == COLS
            assert sum(1 for v in row if v != 0) == 5
        for c in range(COLS):
            col_vals = [ticket[r][c] for r in range(ROWS) if ticket[r][c] != 0]
            assert len(col_vals) <= 3
            assert col_vals == sorted(col_vals)
            lo, hi = COLUMN_RANGES[c][0], COLUMN_RANGES[c][-1]
            for v in col_vals:
                assert lo <= v <= hi
        for r in range(ROWS):
            for c in range(COLS):
                v = ticket[r][c]
                if v != 0:
                    used.add(v)
    assert used == set(range(1, 91))
