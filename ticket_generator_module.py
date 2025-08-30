import random
from typing import List, Optional

# Column ranges: [1–9], [10–19], …, [80–90]
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

# Full-strip counts per column (sum = 90)
# 1–9: 9 numbers, 10–79: 10 each, 80–90: 11 numbers
MAX_PER_COLUMN = {0: 9, 8: 11, **{i: 10 for i in range(1, 8)}}


def generate_full_strip() -> List[List[List[Optional[int]]]]:
    """
    Returns a list of 6 tickets (each 3x9 with None for blanks) such that:
      • Each ticket has exactly 15 numbers (5 per row)
      • Each column per ticket has 0–3 numbers
      • Across the whole strip, column totals match MAX_PER_COLUMN
      • All numbers 1..90 are used exactly once in the strip
    """
    for attempt in range(500):
        try:
            col_usage = [0] * 9
            layouts: List[List[List[int]]] = []

            # Build 6 ticket layouts that respect per-strip column caps
            for _ in range(6):
                layout, temp_usage = _make_ticket_layout(col_usage)
                layouts.append(layout)
                for c in range(9):
                    col_usage[c] += temp_usage[c]

            # Pick the exact numbers each column will use (unique, no repeats)
            column_numbers = {
                c: random.sample(COLUMN_RANGES[c], MAX_PER_COLUMN[c])
                for c in range(9)
            }

            # Fill numbers into each ticket according to its layout
            strip: List[List[List[Optional[int]]]] = []
            for layout in layouts:
                ticket: List[List[Optional[int]]] = [[None for _ in range(9)] for _ in range(3)]
                for c in range(9):
                    for r in range(3):
                        if layout[r][c] == 1:
                            ticket[r][c] = column_numbers[c].pop()
                _sort_columns_in_place(ticket)  # ensure ascending top→bottom per column
                strip.append(ticket)

            # Optional: validate correctness (slow; enable if you want)
            # _assert_valid_strip(strip)

            return strip
        except Exception:
            continue

    raise ValueError("Failed to generate valid strip after many attempts")


def _make_ticket_layout(col_usage):
    """
    Build a 3x9 binary layout for a single ticket:
      • exactly 15 ones
      • 5 ones per row
      • up to 3 ones per column
      • never exceed per-strip MAX_PER_COLUMN when added to col_usage
    """
    layout = [[0] * 9 for _ in range(3)]
    row_counts = [0, 0, 0]
    col_counts = [0] * 9
    temp_col_usage = [0] * 9
    filled = 0

    # First pass: try to place at least one per some columns where caps allow
    for col in random.sample(range(9), 9):
        if col_usage[col] + temp_col_usage[col] >= MAX_PER_COLUMN[col]:
            continue
        rows = [r for r in range(3) if row_counts[r] < 5 and col_counts[col] < 3]
        if not rows:
            continue
        r = random.choice(rows)
        layout[r][col] = 1
        row_counts[r] += 1
        col_counts[col] += 1
        temp_col_usage[col] += 1
        filled += 1

    # Fill to 15 cells
    tries = 0
    while filled < 15 and tries < 3000:
        possible = [
            (r, c)
            for r in range(3) for c in range(9)
            if layout[r][c] == 0
               and row_counts[r] < 5
               and col_counts[c] < 3
               and (col_usage[c] + temp_col_usage[c] < MAX_PER_COLUMN[c])
        ]
        if not possible:
            break
        r, c = random.choice(possible)
        layout[r][c] = 1
        row_counts[r] += 1
        col_counts[c] += 1
        temp_col_usage[c] += 1
        filled += 1
        tries += 1

    if filled == 15 and row_counts == [5, 5, 5]:
        return layout, temp_col_usage
    raise RuntimeError("layout failed")


def _sort_columns_in_place(ticket: List[List[Optional[int]]]) -> None:
    """
    FIXED: sort each column’s values ascending and place them into the
    rows that already contain numbers, from top row to bottom row.
    """
    for c in range(9):
        rows_with_nums = [r for r in range(3) if ticket[r][c] is not None]
        if not rows_with_nums:
            continue
        sorted_vals = sorted(ticket[r][c] for r in rows_with_nums)
        # assign smallest to the topmost row that has a number, etc.
        for r, val in zip(rows_with_nums, sorted_vals):
            ticket[r][c] = val


# --- Optional developer sanity checks ---
def _assert_valid_strip(strip):
    assert len(strip) == 6
    per_col_total = [0] * 9
    used = set()

    for t in strip:
        # 5 numbers per row
        for r in range(3):
            assert sum(1 for x in t[r] if x is not None) == 5

        # per-column 0..3; values in correct range; no dupes
        for c in range(9):
            cnt = 0
            for r in range(3):
                v = t[r][c]
                if v is not None:
                    cnt += 1
                    assert v in COLUMN_RANGES[c]
                    assert v not in used
                    used.add(v)
            assert 0 <= cnt <= 3
            per_col_total[c] += cnt

    # all numbers 1..90 used exactly once
    assert len(used) == 90
    # column totals match spec
    assert per_col_total == [MAX_PER_COLUMN[i] for i in range(9)]
