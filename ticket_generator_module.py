# ticket_generator_module.py
import random

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

# Per-column totals across an entire strip (6 tickets) — using all 1..90
STRIP_COL_TOTALS = [9, 10, 10, 10, 10, 10, 10, 10, 11]


def _build_counts_matrix():
    """
    Build a 6x9 matrix 'counts[t][c]' (tickets x columns) with:
      - Each ticket sums to 15 (=> 5 nums per row x 3 rows)
      - In each ticket, every column has 1..3 numbers (no empty columns)
      - Across tickets, each column sums to STRIP_COL_TOTALS[c]
    """
    T = 6
    C = 9

    # Start with 1 per column per ticket (no blank column)
    counts = [[1 for _ in range(C)] for _ in range(T)]     # baseline 9 per ticket

    # Each ticket needs +6 increments to reach 15
    inc_left_ticket = [6] * T

    # Each column still needs D[c] increments to reach strip total
    D = [STRIP_COL_TOTALS[c] - T for c in range(C)]        # since baseline added T=6 per col
    assert sum(D) == sum(inc_left_ticket), "increments mismatch"

    # Greedy distribute column increments to tickets
    # Always give next increment of column c to a ticket that:
    # - still has increments left
    # - hasn't reached 3 in that column
    # - prefer ticket with the most increments left (balance)
    stalled_passes = 0
    while sum(D) > 0:
        made_progress = False
        cols = list(range(C))
        random.shuffle(cols)
        for c in cols:
            while D[c] > 0:
                # choose ticket with max inc_left that can accept one more in this column
                options = [t for t in range(T) if inc_left_ticket[t] > 0 and counts[t][c] < 3]
                if not options:
                    break
                options.sort(key=lambda t: (-inc_left_ticket[t], counts[t][c]))
                t = options[0]
                counts[t][c] += 1
                inc_left_ticket[t] -= 1
                D[c] -= 1
                made_progress = True
        if not made_progress:
            stalled_passes += 1
            if stalled_passes > 3:
                # give up and start over
                return None

    # Sanity checks
    if any(x != 0 for x in inc_left_ticket):
        return None
    for row in counts:
        if sum(row) != 15:
            return None
        if any(not (1 <= v <= 3) for v in row):
            return None
    for c in range(C):
        if sum(counts[t][c] for t in range(T)) != STRIP_COL_TOTALS[c]:
            return None

    return counts


def _assign_rows_for_ticket(col_counts):
    """
    Given col_counts[9] with values in 1..3 summing to 15,
    choose which rows (0..2) each column occupies so that
    each row ends up with exactly 5 numbers.
    Returns a 3x9 matrix of 0/1.
    """
    R, C = 3, 9
    grid = [[0] * C for _ in range(R)]
    row_sums = [0, 0, 0]

    # Columns with 3 first -> must occupy all 3 rows
    for c in range(C):
        if col_counts[c] == 3:
            for r in range(R):
                grid[r][c] = 1
            row_sums = [x + 1 for x in row_sums]

    # Then columns with 2 -> pick two smallest rows
    for c in range(C):
        if col_counts[c] == 2:
            # pick two rows with minimal row_sums (tie broken randomly)
            rows = list(range(R))
            random.shuffle(rows)
            rows.sort(key=lambda r: row_sums[r])
            for r in rows[:2]:
                grid[r][c] = 1
                row_sums[r] += 1

    # Finally columns with 1 -> pick the smallest row
    for c in range(C):
        if col_counts[c] == 1:
            rows = list(range(R))
            random.shuffle(rows)
            rows.sort(key=lambda r: row_sums[r])
            r = rows[0]
            grid[r][c] = 1
            row_sums[r] += 1

    # Validate exact row sums
    return grid if row_sums == [5, 5, 5] else None


def generate_full_strip():
    """
    Return a list of 6 tickets. Each ticket is 3x9, blank=0.
    Satisfies all Housie strip constraints described above.
    """
    # Try a few attempts in case a random assignment can't be row-balanced
    for _attempt in range(100):
        counts = _build_counts_matrix()
        if counts is None:
            continue

        # Build per-column number pools (use every number exactly once)
        pools = {c: COLUMN_RANGES[c][:] for c in range(9)}
        for c in pools:
            random.shuffle(pools[c])

        strip = []
        for t in range(6):
            col_counts = counts[t]
            row_grid = _assign_rows_for_ticket(col_counts)
            if row_grid is None:
                strip = None
                break

            # Prepare empty 3x9 ticket with zeros as blanks
            ticket = [[0] * 9 for _ in range(3)]

            # For each column, pull the exact amount from pool and place
            for c in range(9):
                need = col_counts[c]
                chosen = [pools[c].pop() for _ in range(need)]
                chosen.sort()  # ascending
                # place chosen numbers into the rows where grid[r][c] == 1, top-to-bottom
                target_rows = [r for r in range(3) if row_grid[r][c] == 1]
                target_rows.sort()
                for val, r in zip(chosen, target_rows):
                    ticket[r][c] = val

            strip.append(ticket)

        if strip is None:
            continue

        # Final validation (belt & braces)
        ok, _ = validate_strip(strip)
        if ok:
            return strip

    raise ValueError("Failed to generate a valid strip after many attempts")


# ---------- Validator (used by /api/selftest and during generation) ----------

def validate_strip(strip):
    """
    strip: list of 6 tickets (each 3x9, blanks = 0)
    Returns (ok: bool, details: dict)
    """
    if len(strip) != 6:
        return False, {"error": "strip_not_6_tickets"}

    # 1..90 exactly once
    seen = set()
    col_totals = [0] * 9
    for t_idx, ticket in enumerate(strip):
        # shape
        if len(ticket) != 3 or any(len(row) != 9 for row in ticket):
            return False, {"error": "bad_shape", "ticket": t_idx}

        # row counts
        for r in range(3):
            row_nums = [x for x in ticket[r] if x != 0]
            if len(row_nums) != 5:
                return False, {"error": "row_count", "ticket": t_idx, "row": r, "count": len(row_nums)}

        # col rules & ascending
        for c in range(9):
            col_vals = [ticket[r][c] for r in range(3) if ticket[r][c] != 0]
            # must be 1..3 per ticket column
            if not (1 <= len(col_vals) <= 3):
                return False, {"error": "col_1_3", "ticket": t_idx, "col": c, "count": len(col_vals)}
            # within range
            low, high = COLUMN_RANGES[c][0], COLUMN_RANGES[c][-1]
            if any(not (low <= v <= high) for v in col_vals):
                return False, {"error": "range", "ticket": t_idx, "col": c, "vals": col_vals}
            # ascending top->bottom
            ordered = sorted(col_vals)
            if col_vals != ordered:
                return False, {"error": "not_sorted", "ticket": t_idx, "col": c, "vals": col_vals}

            col_totals[c] += len(col_vals)

            # track uniqueness
            for v in col_vals:
                if v in seen:
                    return False, {"error": "duplicate", "value": v}
                seen.add(v)

    # exactly 90 unique numbers
    if seen != set(range(1, 91)):
        missing = sorted(set(range(1, 91)) - seen)
        extra = sorted(seen - set(range(1, 91)))
        return False, {"error": "not_1_to_90_once", "missing": missing, "extra": extra}

    # per-column totals for the whole strip
    if col_totals != STRIP_COL_TOTALS:
        return False, {"error": "strip_col_totals", "totals": col_totals, "expected": STRIP_COL_TOTALS}

    return True, {"totals": col_totals}
