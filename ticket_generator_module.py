# ticket_generator_module.py
import random
from typing import List, Optional, Tuple

# Column ranges (inclusive)
COL_RANGES = [
    (1, 9),   # col 0
    (10, 19), # col 1
    (20, 29), # col 2
    (30, 39), # col 3
    (40, 49), # col 4
    (50, 59), # col 5
    (60, 69), # col 6
    (70, 79), # col 7
    (80, 90), # col 8
]

# Target totals across the whole strip (6 tickets) per column:
# 9 + 10*7 + 11 = 90 (each number 1..90 exactly once)
STRIP_COL_TOTALS = [9, 10, 10, 10, 10, 10, 10, 10, 11]

# ------------------------- VALIDATION -------------------------

def _in_col_range(c: int, n: int) -> bool:
    lo, hi = COL_RANGES[c]
    return lo <= n <= hi

def validate_strip(strip: List[List[List[Optional[int]]]]) -> Tuple[bool, str]:
    """
    Validate a strip of 6 tickets with rules:
      - strip has 6 tickets
      - each ticket is 3 x 9
      - each row has exactly 5 numbers
      - each column in a ticket has 1..3 numbers (no all-blank columns)
      - column ranges per number respected
      - across the strip: numbers 1..90 used exactly once
      - across the strip: per-column totals equal STRIP_COL_TOTALS
      - within each ticket column, numbers ascend top->bottom ignoring blanks
    """
    if not isinstance(strip, list) or len(strip) != 6:
        return False, "strip must contain 6 tickets"

    # per-strip uniqueness check
    seen = set()

    # per-strip column totals
    col_totals = [0] * 9

    for t_idx, ticket in enumerate(strip):
        if not isinstance(ticket, list) or len(ticket) != 3:
            return False, f"ticket {t_idx}: not 3 rows"
        for r in range(3):
            if not isinstance(ticket[r], list) or len(ticket[r]) != 9:
                return False, f"ticket {t_idx}: row {r} not 9 cols"

        # rows: exactly 5 numbers
        row_counts = [sum(1 for x in row if x) for row in ticket]
        if any(c != 5 for c in row_counts):
            return False, f"ticket {t_idx}: each row must have 5 numbers"

        # columns: 1..3 per ticket, ranges & ascending
        for c in range(9):
            col_vals = [ticket[r][c] for r in range(3) if ticket[r][c]]
            k = len(col_vals)
            if k < 1 or k > 3:
                return False, f"ticket {t_idx}: column {c} has {k} numbers (must be 1..3)"
            if not all(_in_col_range(c, n) for n in col_vals):
                return False, f"ticket {t_idx}: column {c} has value out of range"
            if col_vals != sorted(col_vals):
                return False, f"ticket {t_idx}: column {c} not ascending"
            col_totals[c] += k

            # add to global seen
            for n in col_vals:
                if n in seen:
                    return False, f"duplicate number {n} in strip"
                seen.add(n)

    # strip must be exactly numbers 1..90
    if seen != set(range(1, 91)):
        missing = [n for n in range(1, 91) if n not in seen]
        extra   = [n for n in sorted(seen) if n < 1 or n > 90]
        return False, f"strip numbers mismatch (missing={missing[:5]}..., extra={extra[:5]}...)"

    if col_totals != STRIP_COL_TOTALS:
        return False, f"strip column totals {col_totals} != {STRIP_COL_TOTALS}"

    return True, "ok"

# ------------------------- GENERATION -------------------------

def _alloc_strip_col_counts() -> List[List[int]]:
    """
    Allocate per-column counts to 6 tickets.
    Matrix A[6][9], each entry in {1,2,3} (no empty columns),
    column sums equal STRIP_COL_TOTALS, and per-ticket total equals 15.
    Solve by backtracking on columns with feasibility pruning.
    """
    TICKETS = 6
    COLS = 9
    target = STRIP_COL_TOTALS[:]              # per-column totals
    used_per_ticket = [0]*TICKETS             # sum across columns must end at 15 each
    A = [[0]*COLS for _ in range(TICKETS)]    # result

    def backtrack_col(c: int) -> bool:
        if c == COLS:
            # all columns assigned; check per-ticket sums
            return all(u == 15 for u in used_per_ticket)

        need = target[c]           # sum for this column
        remaining_cols = COLS - (c + 1)

        # recursive assign a[0..5] in [1..3], sum = need, capacity respected
        vec = [0]*TICKETS

        # To prune, precompute min/max feasible add for each ticket with remaining cols
        min_after = remaining_cols * 1
        max_after = remaining_cols * 3

        def assign_t(ti: int, left: int) -> bool:
            if ti == TICKETS:
                if left == 0:
                    # check feasibility for all tickets for remaining columns
                    for t in range(TICKETS):
                        total_now = used_per_ticket[t] + vec[t]
                        if total_now > 15:
                            return False
                        # remaining must be fillable to hit 15
                        min_need = 15 - total_now - max_after
                        max_need = 15 - total_now - min_after
                        # we need some remaining columns to exist; min_need <= 0 <= max_need
                        if min_need > 0 or max_need < 0:
                            return False
                    # commit this column
                    for t in range(TICKETS):
                        A[t][c] = vec[t]
                        used_per_ticket[t] += vec[t]
                    ok = backtrack_col(c+1)
                    if not ok:
                        # rollback
                        for t in range(TICKETS):
                            used_per_ticket[t] -= vec[t]
                            A[t][c] = 0
                    return ok
                return False

            # Each ticket must get 1..3 in this column
            # Also cannot exceed ticket capacity: used + x + min_after <= 15
            u = used_per_ticket[ti]
            max_x = min(3, 15 - u - min_after)
            min_x = max(1, 15 - u - max_after)
            if max_x < 1: max_x = 1
            if min_x > 3: min_x = 3
            lo = max(1, min_x)
            hi = min(3, max_x)

            # additionally, keep enough left for remaining tickets (at least 1 each)
            remaining_tickets = TICKETS - ti - 1

            for x in (1,2,3):
                if x < lo or x > hi:
                    continue
                if x > left:
                    continue
                # ensure we can give at least 1 to everyone else
                if left - x < remaining_tickets * 1:
                    continue
                # ensure we won't be forced to give more than 3 to someone
                if left - x > remaining_tickets * 3:
                    continue
                vec[ti] = x
                if assign_t(ti+1, left - x):
                    return True
                vec[ti] = 0
            return False

        return assign_t(0, need)

    ok = backtrack_col(0)
    if not ok:
        raise ValueError("Failed to allocate strip column counts")
    return A  # 6x9, values in {1,2,3}, per-ticket sum=15

def _mask_for_ticket(col_sums: List[int]) -> List[List[int]]:
    """
    Given per-column sums (each 1..3) for one ticket, create a 3x9 0/1 mask
    where each row sums to 5 and each column sums to the given number.
    Backtracking on columns; choose which rows receive the 1s.
    """
    rows_left = [5,5,5]
    mask = [[0]*9 for _ in range(3)]

    def choose_rows_for_col(c: int) -> bool:
        if c == 9:
            return rows_left == [0,0,0]
        k = col_sums[c]  # how many rows must be 1 in this column (1..3)

        # pick k distinct rows with rows_left>0
        rows = [0,1,2]
        from itertools import combinations
        for comb in combinations(rows, k):
            # check capacity
            if any(rows_left[r] <= 0 for r in comb):
                continue
            # apply
            for r in comb:
                mask[r][c] = 1
                rows_left[r] -= 1
            # prune: remaining columns must be able to fill remaining row slots
            rem_cols = 9 - (c + 1)
            need_sum = sum(rows_left)
            # each remaining column contributes at least 1 and at most 3 to the strip,
            # but per ticket we only care that total 15 is achievable. At this stage,
            # we only ensure we don't need more than rem_cols*3 or less than rem_cols*1.
            if need_sum >= 0 and need_sum <= rem_cols*3:
                if need_sum >= rem_cols*1:
                    if choose_rows_for_col(c+1):
                        return True
            # rollback
            for r in comb:
                mask[r][c] = 0
                rows_left[r] += 1
        return False

    if not choose_rows_for_col(0):
        raise ValueError("Failed to build row mask for ticket")
    return mask

def generate_full_strip() -> List[List[List[Optional[int]]]]:
    """
    Generate one full strip (6 tickets), fully valid per rules.
    """
    # 1) Decide how many numbers each column contributes to each of the 6 tickets
    alloc = _alloc_strip_col_counts()  # [6][9] in {1,2,3}, each ticket sums to 15

    # 2) Pre-generate column pools for the entire strip (unique numbers)
    pools = []
    for c in range(9):
        lo, hi = COL_RANGES[c]
        nums = list(range(lo, hi+1))
        random.shuffle(nums)
        # take exactly STRIP_COL_TOTALS[c] numbers from this column
        pools.append(nums[:STRIP_COL_TOTALS[c]])

    # 3) For each ticket build a 3x9 mask matching column sums, then fill numbers
    strip = []
    # track how many consumed from each column pool so far
    consumed = [0]*9

    for t in range(6):
        col_sums = alloc[t]  # len 9, each 1..3, sums to 15
        mask = _mask_for_ticket(col_sums)

        # create empty 3x9 ticket
        ticket: List[List[Optional[int]]] = [[None]*9 for _ in range(3)]

        # fill column by column, ascending down the column
        for c in range(9):
            need = col_sums[c]
            take = pools[c][consumed[c]:consumed[c]+need]
            consumed[c] += need
            take.sort()  # ascending downwards
            # place into rows where mask==1
            rows = [r for r in range(3) if mask[r][c] == 1]
            for r, val in zip(rows, take):
                ticket[r][c] = val

        strip.append(ticket)

    # final safety check
    ok, msg = validate_strip(strip)
    if not ok:
        raise ValueError(f"Generated strip failed validation: {msg}")
    return strip
