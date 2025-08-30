# ticket_generator_module.py
# Generates a valid Housie90 strip (6 tickets) with hard guarantees:
# - 6 tickets, each 3x9, rows have exactly 5 numbers (15 per ticket)
# - Columns use ranges: [1-9], [10-19], ..., [80-90]
# - Across the strip, each number 1..90 used exactly once
# - Per ticket, per column <= 3 numbers, and columns ascend top->bottom
# - Blanks are 0

import random
from typing import List, Optional, Tuple
from itertools import combinations

TICKETS_PER_STRIP = 6
ROWS = 3
COLS = 9

# Column ranges
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
# Totals per column across the 6-ticket strip
COLUMN_TOTALS = [len(COLUMN_RANGES[c]) for c in range(COLS)]  # [9,10,10,10,10,10,10,10,11]

def generate_full_strip() -> List[List[List[Optional[int]]]]:
    """
    Returns a list of 6 tickets, each ticket is a 3x9 list of ints (0 for blank).
    """
    # Try a few randomized attempts to find a valid allocation quickly
    for _ in range(200):
        try:
            # Step A: decide counts per ticket per column (values 0..3)
            counts = _allocate_col_counts()

            # Step B: for each ticket, choose which rows get the numbers (to end with 5 per row)
            layouts = [_assign_rows_for_ticket(counts[t]) for t in range(TICKETS_PER_STRIP)]

            # Step C: place the actual numbers, preserving ascending order in each ticket column
            strip = _fill_numbers(layouts)

            # Final sanity check (defensive)
            _verify_strip(strip)
            return strip
        except Exception:
            continue
    raise ValueError("Failed to generate a valid housie strip after many attempts")

# -----------------------------
# Step A: allocate counts per ticket per column
# -----------------------------
def _allocate_col_counts() -> List[List[int]]:
    """
    Build a 6x9 matrix 'counts' where counts[t][c] in {0..3},
    sum_t counts[t][c] == COLUMN_TOTALS[c],
    and sum_c counts[t][c] == 15 for every ticket t.
    """
    counts = [[0]*COLS for _ in range(TICKETS_PER_STRIP)]
    ticket_sums = [0]*TICKETS_PER_STRIP

    col_order = list(range(COLS))
    # Work hardest columns first (11 then 10 then 9) helps pruning
    col_order.sort(key=lambda c: COLUMN_TOTALS[c], reverse=True)

    def dfs(ci: int) -> bool:
        if ci == COLS:
            return all(s == 15 for s in ticket_sums)

        c = col_order[ci]
        need = COLUMN_TOTALS[c]

        # Choose a per-ticket distribution for this column
        ticket_order = list(range(TICKETS_PER_STRIP))
        random.shuffle(ticket_order)

        # Prepare a holder for this column's assignment
        col_counts = [0] * TICKETS_PER_STRIP

        def place_for_ticket(i: int, remaining: int) -> bool:
            if i == TICKETS_PER_STRIP:
                if remaining != 0:
                    return False
                # Feasibility check for the future columns
                remaining_cols = COLS - (ci + 1)
                for t in range(TICKETS_PER_STRIP):
                    s2 = ticket_sums[t] + col_counts[t]
                    if s2 > 15:
                        return False
                    if 15 - s2 > 3 * remaining_cols:
                        return False
                # Commit this column
                for t in range(TICKETS_PER_STRIP):
                    counts[t][c] = col_counts[t]
                    ticket_sums[t] += col_counts[t]
                ok = dfs(ci + 1)
                if not ok:
                    # rollback
                    for t in range(TICKETS_PER_STRIP):
                        ticket_sums[t] -= col_counts[t]
                        counts[t][c] = 0
                return ok

            t = ticket_order[i]
            remaining_cols = COLS - (ci + 1)
            need_ticket = 15 - ticket_sums[t]

            # tight lower bound now to stay feasible later:
            min_x = max(0, need_ticket - 3 * remaining_cols)
            min_x = max(0, min_x)  # non-negative
            max_x = min(3, remaining, need_ticket)

            if min_x > max_x:
                return False

            # Try a few values in a shuffled order to add randomness
            choices = list(range(min_x, max_x + 1))
            random.shuffle(choices)
            # Bias towards mid/high fills a bit to avoid starving tickets
            choices.sort(reverse=True)

            for x in choices:
                col_counts[t] = x
                if place_for_ticket(i + 1, remaining - x):
                    return True
            col_counts[t] = 0
            return False

        return place_for_ticket(0, need)

    ok = dfs(0)
    if not ok:
        raise ValueError("count allocation failed")
    return counts

# -----------------------------
# Step B: assign rows inside each ticket
# -----------------------------
def _assign_rows_for_ticket(col_counts: List[int]) -> List[List[int]]:
    """
    For one ticket: given counts per column (0..3), choose rows for those
    cells so that each row ends with exactly 5 numbers.
    Returns a 3x9 layout of 0/1s.
    """
    layout = [[0]*COLS for _ in range(ROWS)]
    rows_left = [5, 5, 5]  # each row needs 5
    cols_with_counts = [c for c in range(COLS) if col_counts[c] > 0]
    # Place larger columns first (3 then 2 then 1) to reduce branching
    cols_with_counts.sort(key=lambda c: col_counts[c], reverse=True)

    total_to_place = sum(col_counts)

    def feasible_after(i: int) -> bool:
        # basic prune: each row r can get at most (remaining_cols) more cells
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

        # helper to commit picks for this column
        def apply_rows(rows: Tuple[int, ...], on: bool):
            delta = 1 if on else -1
            for r in rows:
                layout[r][c] = 1 if on else 0
                rows_left[r] -= delta

        # Enumerate row choices by k
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
            # Try the row with the most remaining first
            candidates.sort(key=lambda r: rows_left[r], reverse=True)
            for r in candidates:
                apply_rows((r,), True)
                if dfs(i + 1, placed + 1):
                    return True
                apply_rows((r,), False)
            return False

        # k==0 should not be here, but handle gracefully
        return dfs(i + 1, placed)

    ok = dfs(0, 0)
    if not ok:
        raise ValueError("row assignment failed")
    return layout

# -----------------------------
# Step C: fill numbers into layouts
# -----------------------------
def _fill_numbers(layouts: List[List[List[int]]]) -> List[List[List[int]]]:
    """
    layouts: list of 6 items; each is 3x9 0/1 grid.
    Fills numbers from COLUMN_RANGES, 1..90 used once in the strip,
    columns ascending inside each ticket. Returns 6 tickets with ints (0 for blanks).
    """
    # Prepare per-column number pools and shuffle for randomness
    pools = {c: COLUMN_RANGES[c][:] for c in range(COLS)}
    for c in range(COLS):
        random.shuffle(pools[c])

    # Start with 6 empty tickets
    strip = [[[0]*COLS for _ in range(ROWS)] for _ in range(TICKETS_PER_STRIP)]

    for c in range(COLS):
        pool = pools[c]
        idx = 0  # index into the shuffled pool

        # For each ticket, collect how many numbers and their row indexes
        per_ticket_rows = []
        for t in range(TICKETS_PER_STRIP):
            rows_here = [r for r in range(ROWS) if layouts[t][r][c] == 1]
            per_ticket_rows.append((t, rows_here))

        # Randomize ticket order for variety
        random.shuffle(per_ticket_rows)

        for t, rows_here in per_ticket_rows:
            k = len(rows_here)
            if k == 0:
                continue
            # take k numbers from pool
            chosen = pool[idx: idx + k]
            idx += k
            chosen.sort()  # ensure ascending inside the ticket column

            # place ascending downwards by row index
            rows_here_sorted = sorted(rows_here)
            for rr, val in zip(rows_here_sorted, chosen):
                strip[t][rr][c] = val

        # guard: we must have used exactly COLUMN_TOTALS[c] numbers
        if idx != COLUMN_TOTALS[c]:
            # should not happen; raise to trigger a retry
            raise ValueError("column fill mismatch")

    return strip

# -----------------------------
# Validation (used internally)
# -----------------------------
def _verify_strip(strip: List[List[List[int]]]) -> None:
    # 6 tickets
    assert len(strip) == TICKETS_PER_STRIP
    used = set()

    # Check each ticket
    for t in range(TICKETS_PER_STRIP):
        ticket = strip[t]
        assert len(ticket) == ROWS
        for r in range(ROWS):
            row = ticket[r]
            assert len(row) == COLS
            # exactly 5 numbers per row
            assert sum(1 for v in row if v != 0) == 5

        # per column <=3, ascending, and within range
        for c in range(COLS):
            col_vals = [ticket[r][c] for r in range(ROWS) if ticket[r][c] != 0]
            assert len(col_vals) <= 3
            assert col_vals == sorted(col_vals)
            # range check
            lo = COLUMN_RANGES[c][0]
            hi = COLUMN_RANGES[c][-1]
            for v in col_vals:
                assert lo <= v <= hi

        # collect used numbers
        for r in range(ROWS):
            for c in range(COLS):
                v = ticket[r][c]
                if v != 0:
                    used.add(v)

    # across strip: 1..90 used exactly once
    assert used == set(range(1, 91))
