# ticket_generator_module.py
import random
from typing import List, Optional, Tuple

# Column ranges (inclusive)
COL_RANGES = [
    list(range(1, 10)),   # 1–9
    list(range(10, 20)),  # 10–19
    list(range(20, 30)),  # 20–29
    list(range(30, 40)),  # 30–39
    list(range(40, 50)),  # 40–49
    list(range(50, 60)),  # 50–59
    list(range(60, 70)),  # 60–69
    list(range(70, 80)),  # 70–79
    list(range(80, 91)),  # 80–90
]

# Required strip column totals across 6 tickets:
# col0=9, col1..col7=10, col8=11  => sums to 90 numbers per strip
STRIP_QUOTAS = [9, 10, 10, 10, 10, 10, 10, 10, 11]

# For each quota, use a 6-length vector of 0/1/2 that sums to quota (each ticket col <=2).
TEMPLATES = {
    9:  [2, 2, 2, 1, 1, 1],      # 3x2 + 3x1 = 9
    10: [2, 2, 2, 2, 1, 1],      # 4x2 + 2x1 = 10
    11: [2, 2, 2, 2, 2, 1],      # 5x2 + 1x1 = 11
}


def _balanced_column_distribution() -> List[List[int]]:
    """
    Build a 9 x 6 matrix 'dist' where dist[c][t] ∈ {0,1,2}:
      - For each column c, the 6 entries sum to STRIP_QUOTAS[c]
      - Per ticket (t), the sum across columns equals 15
    We use a greedy balancing assignment across columns.
    """
    for attempt in range(200):
        totals = [0] * 6                          # numbers per ticket (want 15 each)
        dist = [[0]*6 for _ in range(9)]          # 9 columns x 6 tickets

        ok = True
        order = list(range(6))

        for c, quota in enumerate(STRIP_QUOTAS):
            base = TEMPLATES[quota][:]            # e.g., [2,2,2,1,1,1]
            # shuffle ties a bit to avoid deterministic patterns
            random.shuffle(order)
            # sort ticket indices by who has the *fewest* numbers so far
            idxs = sorted(order, key=lambda t: totals[t])

            # place 2s on the "neediest" tickets, then 1s, rest 0
            k2 = base.count(2)
            k1 = base.count(1)

            twos = idxs[:k2]
            ones = idxs[k2:k2+k1]

            for t in twos:
                dist[c][t] = 2
                totals[t] += 2
            for t in ones:
                dist[c][t] = 1
                totals[t] += 1

        if all(t == 15 for t in totals):
            return dist
        # otherwise try again
    raise ValueError("Could not balance per-ticket totals to 15 after many attempts")


def _assign_rows_for_ticket(col_counts: List[int]) -> List[List[int]]:
    """
    Given a list col_counts[9] of {0,1,2} for a single ticket,
    return a 3x9 0/1 layout with exactly 5 ones per row and
    exactly col_counts[c] ones in each column c.
    Greedy with retries.
    """
    for attempt in range(300):
        rows_left = [5, 5, 5]  # each row must end up with 5
        layout = [[0]*9 for _ in range(3)]

        # Place 2s first (need two distinct rows), then 1s.
        cols2 = [c for c, v in enumerate(col_counts) if v == 2]
        cols1 = [c for c, v in enumerate(col_counts) if v == 1]
        random.shuffle(cols2)
        random.shuffle(cols1)

        # Place the 2s
        ok = True
        for c in cols2:
            # pick two distinct rows with the most capacity
            candidate_rows = sorted(range(3), key=lambda r: rows_left[r], reverse=True)
            # we need two rows with >0 capacity
            picks = []
            for r in candidate_rows:
                if rows_left[r] > 0:
                    picks.append(r)
                if len(picks) == 2:
                    break
            if len(picks) < 2:
                ok = False
                break
            r1, r2 = picks
            layout[r1][c] = 1
            layout[r2][c] = 1
            rows_left[r1] -= 1
            rows_left[r2] -= 1
        if not ok:
            continue

        # Place the 1s
        for c in cols1:
            # pick the row with the most capacity
            r = max(range(3), key=lambda rr: rows_left[rr])
            if rows_left[r] == 0:
                ok = False
                break
            layout[r][c] = 1
            rows_left[r] -= 1
        if not ok:
            continue

        # All rows must be exactly 5
        if rows_left == [0, 0, 0]:
            return layout

    raise ValueError("Row assignment failed for a ticket after many attempts")


def generate_full_strip() -> List[List[List[Optional[int]]]]:
    """
    Returns a strip: list of 6 tickets; each ticket is 3x9 with ints or None.
    Satisfies:
      - Each ticket row has exactly 5 numbers
      - Each ticket column has at most 2 numbers
      - Strip column totals equal STRIP_QUOTAS
      - Numbers respect column ranges and are sorted top→bottom per column
    """
    # 1) Decide how many numbers each ticket gets in each column (dist 9x6)
    dist = _balanced_column_distribution()  # dist[c][t] in {0,1,2}

    # 2) Build per-ticket 3x9 layouts matching dist and rows=5 each
    ticket_layouts = []
    for t in range(6):
        col_counts = [dist[c][t] for c in range(9)]
        layout = _assign_rows_for_ticket(col_counts)  # 3x9 0/1
        ticket_layouts.append(layout)

    # 3) Pick actual numbers for each column (strip-level), then fill tickets
    col_pools = []
    for c, quota in enumerate(STRIP_QUOTAS):
        pool = random.sample(COL_RANGES[c], quota)
        pool.sort()
        col_pools.append(pool)

    # pointers per col into the strip pool
    col_ptr = [0] * 9

    # allocate numbers ticket by ticket, col by col, top→bottom within the column
    strip = []
    for t in range(6):
        layout = ticket_layouts[t]
        # initialize with Nones
        ticket = [[None]*9 for _ in range(3)]
        for c in range(9):
            # rows where this ticket has a '1' in that column
            rows = [r for r in range(3) if layout[r][c] == 1]
            rows.sort()  # ensure ascending rows -> ascending numbers
            for r in rows:
                ticket[r][c] = col_pools[c][col_ptr[c]]
                col_ptr[c] += 1
        strip.append(ticket)

    return strip


# --------- Optional: strip validator for debugging/self-test ----------
def validate_strip(strip: List[List[List[Optional[int]]]]) -> Tuple[bool, bool, List[int]]:
    """Return (rows_ok, per_ticket_cols_ok, strip_col_totals)."""
    # rows=5 each
    rows_ok = all(
        sum(1 for v in row if v is not None) == 5
        for ticket in strip for row in ticket
    )

    # per-ticket, each column <= 2
    per_ticket_cols_ok = all(
        all(sum(1 for r in range(3) if ticket[r][c] is not None) <= 2 for c in range(9))
        for ticket in strip
    )

    # strip column totals
    col_totals = [0]*9
    for ticket in strip:
        for r in range(3):
            for c in range(9):
                if ticket[r][c] is not None:
                    col_totals[c] += 1

    return rows_ok, per_ticket_cols_ok, col_totals
