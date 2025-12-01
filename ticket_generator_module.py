# ticket_generator_module.py
import random
from typing import List, Optional, Tuple
from itertools import combinations

# Column ranges (inclusive) for 9 columns:
# 0: 1–9, 1: 10–19, ..., 8: 80–90
COL_RANGES: List[Tuple[int, int]] = [
    (1, 9),    # col 0
    (10, 19),  # col 1
    (20, 29),  # col 2
    (30, 39),  # col 3
    (40, 49),  # col 4
    (50, 59),  # col 5
    (60, 69),  # col 6
    (70, 79),  # col 7
    (80, 90),  # col 8
]

# Target totals across the whole strip (6 tickets) per column:
# 9 + 10*7 + 11 = 90 (each number 1..90 appears exactly once)
STRIP_COL_TOTALS: List[int] = [9, 10, 10, 10, 10, 10, 10, 10, 11]


# ========================= VALIDATION =========================

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

    seen = set()              # global uniqueness
    col_totals = [0] * 9      # per-strip column totals

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

        # columns: 1..3 per ticket, ranges & ascending, and contribute to strip totals
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

            # global uniqueness
            for n in col_vals:
                if n in seen:
                    return False, f"duplicate number {n} in strip"
                seen.add(n)

    # strip must be exactly numbers 1..90
    if seen != set(range(1, 91)):
        missing = [n for n in range(1, 91) if n not in seen]
        extra = [n for n in sorted(seen) if n < 1 or n > 90]
        return False, f"strip numbers mismatch (missing={missing[:5]}..., extra={extra[:5]}...)"

    if col_totals != STRIP_COL_TOTALS:
        return False, f"strip column totals {col_totals} != {STRIP_COL_TOTALS}"

    return True, "ok"


# ========================= BALANCE HELPERS =========================

def _ticket_block_counts(ticket: List[List[Optional[int]]]) -> Tuple[int, int, int]:
    """
    Count how many numbers are in each 3-column block:
      - Left:   cols 0,1,2
      - Middle: cols 3,4,5
      - Right:  cols 6,7,8
    """
    left = mid = right = 0
    for r in range(3):
        for c in range(9):
            if ticket[r][c]:
                if c <= 2:
                    left += 1
                elif c <= 5:
                    mid += 1
                else:
                    right += 1
    return left, mid, right


def _is_balanced_ticket(ticket: List[List[Optional[int]]]) -> bool:
    """
    A ticket is 'balanced' if the distribution of numbers across
    left/middle/right blocks is not too extreme.
    Condition: max(block) - min(block) <= 2
    This avoids tickets heavily skewed to left or right.
    """
    left, mid, right = _ticket_block_counts(ticket)
    mx = max(left, mid, right)
    mn = min(left, mid, right)
    return (mx - mn) <= 2


# ========================= GENERATION =========================

def _alloc_strip_col_counts() -> List[List[int]]:
    """
    Allocate per-column counts to 6 tickets.

    Returns A[6][9] such that:
      - A[t][c] in {1,2,3} (each ticket uses that column at least once)
      - For each column c, sum_t A[t][c] = STRIP_COL_TOTALS[c]
      - For each ticket t, sum_c A[t][c] = 15  (15 numbers per ticket)

    This uses backtracking over columns with feasibility pruning.
    """
    TICKETS = 6
    COLS = 9
    target = STRIP_COL_TOTALS[:]  # per-column totals
    A = [[0] * COLS for _ in range(TICKETS)]
    used_per_ticket = [0] * TICKETS

    def compositions_of_total(total: int, k: int) -> List[List[int]]:
        """
        All k-length lists of integers in [1,3] that sum to total.
        Used for one column (6 tickets).
        """
        result: List[List[int]] = []

        def rec(i: int, rem: int, cur: List[int]):
            if i == k:
                if rem == 0:
                    result.append(cur[:])
                return
            # At position i, choose x in [1,3] such that it is still possible
            for x in (1, 2, 3):
                if x > rem:
                    continue
                # min sum for remaining slots = 1*(k-i-1)
                # max sum for remaining slots = 3*(k-i-1)
                rem_after = rem - x
                if rem_after < (k - i - 1) * 1:
                    continue
                if rem_after > (k - i - 1) * 3:
                    continue
                cur.append(x)
                rec(i + 1, rem_after, cur)
                cur.pop()

        rec(0, total, [])
        # Randomize order to vary patterns between runs
        random.shuffle(result)
        return result

    # Precompute possible column distributions for each needed total
    possible_for_total = {
        tot: compositions_of_total(tot, TICKETS) for tot in set(target)
    }

    def backtrack_col(c: int) -> bool:
        if c == COLS:
            # All columns assigned; check each ticket has exactly 15
            return all(u == 15 for u in used_per_ticket)

        need = target[c]
        candidates = possible_for_total[need]

        remaining_cols = COLS - c - 1

        for vec in candidates:
            # Check ticket capacity with this column assignment
            ok = True
            for t in range(TICKETS):
                new_used = used_per_ticket[t] + vec[t]
                if new_used > 15:
                    ok = False
                    break
                if remaining_cols > 0:
                    # remaining numbers needed after this column
                    rem_need = 15 - new_used
                    # min numbers remaining we can still add to this ticket
                    min_possible = remaining_cols * 1
                    max_possible = remaining_cols * 3
                    # rem_need must be in [min_possible, max_possible]
                    if rem_need < min_possible or rem_need > max_possible:
                        ok = False
                        break
                else:
                    # no more columns left; must be exactly 15
                    if new_used != 15:
                        ok = False
                        break
            if not ok:
                continue

            # commit this column
            for t in range(TICKETS):
                A[t][c] = vec[t]
                used_per_ticket[t] += vec[t]

            if backtrack_col(c + 1):
                return True

            # rollback
            for t in range(TICKETS):
                used_per_ticket[t] -= vec[t]
                A[t][c] = 0

        return False

    if not backtrack_col(0):
        raise ValueError("Failed to allocate strip column counts")
    return A  # 6x9, each entry in {1,2,3}


def _mask_for_ticket(col_sums: List[int]) -> List[List[int]]:
    """
    Given per-column sums (each 1..3) for one ticket, create a 3x9 0/1 mask
    where each row sums to 5 and each column sums to the given number.

    mask[r][c] = 1 means there will be a number at (r,c).
    Uses backtracking by columns with simple pruning.
    """
    if len(col_sums) != 9:
        raise ValueError("col_sums must have length 9")
    if sum(col_sums) != 15:
        raise ValueError("sum(col_sums) must be 15 for a ticket")

    rows_left = [5, 5, 5]          # how many cells still needed per row
    mask = [[0] * 9 for _ in range(3)]

    def backtrack(c: int) -> bool:
        if c == 9:
            return rows_left == [0, 0, 0]

        k = col_sums[c]  # how many rows must be 1 in this column (1..3)
        # choose k distinct rows with rows_left > 0
        valid_rows = [r for r in range(3) if rows_left[r] > 0]
        if len(valid_rows) < k:
            return False

        remaining_cols = 8 - c  # columns after this one

        for comb in combinations(valid_rows, k):
            # apply this choice
            for r in comb:
                rows_left[r] -= 1
                mask[r][c] = 1

            # prune: each row can't need more than remaining_cols cells
            feasible = True
            for r in range(3):
                if rows_left[r] < 0:
                    feasible = False
                    break
                if remaining_cols >= 0 and rows_left[r] > remaining_cols:
                    feasible = False
                    break

            if feasible:
                if backtrack(c + 1):
                    return True

            # rollback
            for r in comb:
                rows_left[r] += 1
                mask[r][c] = 0

        return False

    if not backtrack(0):
        raise ValueError("Failed to build row mask for ticket")
    return mask


def generate_full_strip(max_attempts: int = 200) -> List[List[List[Optional[int]]]]:
    """
    Generate one full strip (6 tickets), fully valid per rules AND
    reasonably balanced left/middle/right on each ticket.

    Rules enforced:
      - 6 tickets per strip
      - each ticket is 3x9
      - each row has exactly 5 numbers
      - each column in a ticket has 1..3 numbers
      - each ticket’s columns respect COL_RANGES
      - across the strip: numbers 1..90 used exactly once
      - strip column totals equal STRIP_COL_TOTALS
      - columns in each ticket ascend top->bottom
      - each ticket is 'balanced' across left/middle/right blocks
        (max(block) - min(block) <= 2)

    If no balanced strip is found within max_attempts, but at least one
    strictly valid strip was generated, that last valid strip is returned
    as a fallback.
    """
    last_valid_strip: Optional[List[List[List[Optional[int]]]]] = None
    last_msg: str = "no_attempt"

    for _ in range(max_attempts):
        # 1) Decide how many numbers each column contributes to each of the 6 tickets
        alloc = _alloc_strip_col_counts()  # shape [6][9], entries in {1,2,3}

        # 2) Pre-generate column pools for the entire strip (unique numbers per column)
        pools: List[List[int]] = []
        for c in range(9):
            lo, hi = COL_RANGES[c]
            nums = list(range(lo, hi + 1))
            random.shuffle(nums)
            # take exactly STRIP_COL_TOTALS[c] numbers from this column
            pools.append(nums[:STRIP_COL_TOTALS[c]])

        # 3) For each ticket, build a 3x9 mask matching column sums, then fill numbers
        strip: List[List[List[Optional[int]]]] = []
        consumed = [0] * 9  # how many from each column pool used so far

        try:
            for t in range(6):
                col_sums = alloc[t]  # length 9, in {1..3}, sums to 15
                mask = _mask_for_ticket(col_sums)

                ticket: List[List[Optional[int]]] = [[None] * 9 for _ in range(3)]

                for c in range(9):
                    need = col_sums[c]
                    take = pools[c][consumed[c] : consumed[c] + need]
                    consumed[c] += need
                    take.sort()  # ascending numbers in this column

                    rows = [r for r in range(3) if mask[r][c] == 1]
                    # rows length must equal 'need'
                    for r, val in zip(rows, take):
                        ticket[r][c] = val

                strip.append(ticket)

            ok, msg = validate_strip(strip)
            last_valid_strip, last_msg = (strip, msg)
            if not ok:
                # invalid strip; retry
                continue

            # Additional balance constraint per ticket
            if all(_is_balanced_ticket(t) for t in strip):
                return strip

        except Exception as e:
            last_valid_strip = None
            last_msg = str(e)
            # try again

    # Fallback: if we had at least one strictly valid strip, return it
    if last_valid_strip is not None:
        return last_valid_strip

    raise ValueError(f"Failed to generate balanced strip after {max_attempts} attempts: {last_msg}")
