# ticket_generator_module.py
import random
from typing import List, Optional, Tuple, Dict

Ticket = List[List[Optional[int]]]       # 3 rows x 9 cols, 0 = blank
Strip  = List[Ticket]                     # 6 tickets

COL_RANGES: Dict[int, range] = {
    0: range(1, 10),     # 9
    1: range(10, 20),    # 10
    2: range(20, 30),    # 10
    3: range(30, 40),    # 10
    4: range(40, 50),    # 10
    5: range(50, 60),    # 10
    6: range(60, 70),    # 10
    7: range(70, 80),    # 10
    8: range(80, 91),    # 11  (80..90)
}
COL_TOTALS = [9,10,10,10,10,10,10,10,11]  # per-strip column counts
TICKETS = 6
ROWS    = 3
COLS    = 9

def _balanced_column_assignments() -> List[List[int]]:
    """
    Make a 6x9 matrix 'counts' with values in {1,2} such that:
      - For each column c, sum_t counts[t][c] == COL_TOTALS[c]
      - For each ticket t, sum_c counts[t][c] == 15
      - Thus every ticket has at least 1 in every column (no blank column).
    Strategy:
      * Start with 1 in every cell (base = 6 per column, 9 per ticket)
      * Distribute 'extras' for each column (total[c] - 6) across tickets
        while ensuring each ticket receives exactly 6 extras overall.
    """
    # base ones everywhere
    counts = [[1 for _ in range(COLS)] for _ in range(TICKETS)]
    extras_needed_per_ticket = [6 for _ in range(TICKETS)]  # 9 base -> need +6 = 15

    # randomize column order to vary layouts
    cols_order = list(range(COLS))
    random.shuffle(cols_order)

    for c in cols_order:
        extras = COL_TOTALS[c] - TICKETS  # because base 1 assigned to all 6 tickets
        # choose 'extras' tickets preferring those who still need more extras
        # tie-break randomly
        ticket_ids = list(range(TICKETS))
        random.shuffle(ticket_ids)
        ticket_ids.sort(key=lambda t: extras_needed_per_ticket[t], reverse=True)

        chosen = []
        for t in ticket_ids:
            if extras == 0:
                break
            if extras_needed_per_ticket[t] > 0:
                counts[t][c] += 1
                extras_needed_per_ticket[t] -= 1
                extras -= 1
                chosen.append(t)

        if extras != 0:
            # If we failed to place all extras (shouldn't happen), restart recursively
            return _balanced_column_assignments()

    # Sanity check: each ticket now has exactly 15; each column sums to COL_TOTALS
    for t in range(TICKETS):
        assert sum(counts[t]) == 15, f"ticket {t} not 15 ({sum(counts[t])})"
    for c in range(COLS):
        assert sum(counts[t][c] for t in range(TICKETS)) == COL_TOTALS[c], "col total mismatch"

    return counts

def _fill_rows_for_ticket(col_counts: List[int]) -> List[List[int]]:
    """
    Given 9 integers (each 1 or 2) whose sum is 15, generate a 3x9 0/1 layout with
    each row sum exactly 5 and each column sum == col_counts[c].
    Greedy + retry is enough because counts are gentle (only 1 or 2).
    """
    for _ in range(200):  # retry guard
        layout = [[0]*COLS for _ in range(ROWS)]
        remain = [5,5,5]

        # place columns with 2 first
        two_cols = [c for c,v in enumerate(col_counts) if v == 2]
        random.shuffle(two_cols)
        ok = True
        for c in two_cols:
            # choose two distinct rows with biggest remaining capacity
            rows_sorted = list(range(ROWS))
            random.shuffle(rows_sorted)
            rows_sorted.sort(key=lambda r: remain[r], reverse=True)
            placed = 0
            for r in rows_sorted:
                if remain[r] > 0 and layout[r][c] == 0:
                    layout[r][c] = 1
                    remain[r] -= 1
                    placed += 1
                    if placed == 2:
                        break
            if placed < 2:
                ok = False
                break
        if not ok:
            continue

        # place columns with 1
        one_cols = [c for c,v in enumerate(col_counts) if v == 1]
        random.shuffle(one_cols)
        for c in one_cols:
            rows_sorted = list(range(ROWS))
            random.shuffle(rows_sorted)
            rows_sorted.sort(key=lambda r: remain[r], reverse=True)
            placed = False
            for r in rows_sorted:
                if remain[r] > 0 and layout[r][c] == 0:
                    layout[r][c] = 1
                    remain[r] -= 1
                    placed = True
                    break
            if not placed:
                ok = False
                break
        if not ok:
            continue

        if remain == [0,0,0]:
            return layout

    raise ValueError("row-placement failed")

def _sort_columns_top_down(ticket: Ticket) -> Ticket:
    # sort non-zero values in each column ascending, keep 0s where they are not used
    for c in range(COLS):
        present = [(r, ticket[r][c]) for r in range(ROWS) if ticket[r][c] not in (0, None)]
        values  = sorted(v for _, v in present)
        # write back in row order of existing ones
        i = 0
        for r in range(ROWS):
            if ticket[r][c] not in (0, None):
                ticket[r][c] = values[i]
                i += 1
    return ticket

def generate_full_strip() -> Strip:
    """
    Build a full, valid Housie90 strip (6 tickets) that meets all rules.
    """
    # 1) Pre-shuffle numbers per column
    col_numbers = {c: list(COL_RANGES[c]) for c in range(COLS)}
    for c in range(COLS):
        random.shuffle(col_numbers[c])

    # 2) Decide how many numbers each ticket gets in each column (1 or 2), balanced to 15/strip totals
    counts = _balanced_column_assignments()  # 6 x 9

    # 3) For each ticket, choose rows for those column-counts (row sums = 5)
    layouts = [_fill_rows_for_ticket(counts[t]) for t in range(TICKETS)]  # 6 x (3 x 9)

    # 4) Build tickets, pulling actual numbers from each column
    strip: Strip = []
    for t in range(TICKETS):
        ticket: Ticket = [[0]*COLS for _ in range(ROWS)]
        for c in range(COLS):
            need = counts[t][c]
            # rows where we put 1s
            rows_here = [r for r in range(ROWS) if layouts[t][r][c] == 1]
            assert len(rows_here) == need
            # pop that many numbers from the column pool
            for r in rows_here:
                ticket[r][c] = col_numbers[c].pop()
        strip.append(_sort_columns_top_down(ticket))

    # 5) Final sanity: used all column totals
    for c in range(COLS):
        if len(col_numbers[c]) != len(COL_RANGES[c]) - COL_TOTALS[c]:
            raise AssertionError("Column pool mismatch after fill")

    return strip

# --------- Optional validator (can be used in a /api/selftest) ----------
def validate_strip(strip: Strip) -> Dict[str, object]:
    ok = True
    errors = []

    # a) exactly 6 tickets
    if len(strip) != 6:
        ok = False
        errors.append("Strip must have 6 tickets")

    # b) per ticket rows=3, cols=9; row sums=5; col per ticket in {0..3}
    for ti, t in enumerate(strip):
        if len(t) != 3 or any(len(row) != 9 for row in t):
            ok = False
            errors.append(f"Ticket {ti}: size must be 3x9")
            continue
        row_sums = [sum(1 for v in row if v not in (0, None)) for row in t]
        if row_sums != [5,5,5]:
            ok = False
            errors.append(f"Ticket {ti}: row sums not [5,5,5] -> {row_sums}")
        # no blank columns (per your preference)
        for c in range(9):
            col_count = sum(1 for r in range(3) if t[r][c] not in (0, None))
            if col_count == 0:
                ok = False
                errors.append(f"Ticket {ti}: column {c} is blank")

    # c) strip coverage: exactly numbers 1..90 used once
    seen = []
    for t in strip:
        for r in range(3):
            for c in range(9):
                v = t[r][c]
                if v not in (0, None):
                    seen.append(v)
    if sorted(seen) != list(range(1, 91)):
        ok = False
        errors.append("Strip does not contain exactly 1..90 once each")

    # d) per column totals across strip
    col_totals = [0]*9
    for t in strip:
        for c in range(9):
            col_totals[c] += sum(1 for r in range(3) if t[r][c] not in (0, None))
    if col_totals != COL_TOTALS:
        ok = False
        errors.append(f"Column totals mismatch: {col_totals} != {COL_TOTALS}")

    return {"ok": ok, "errors": errors, "col_totals": col_totals}
