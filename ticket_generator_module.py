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

    seen = set()
    col_totals = [0] * 9

    for t_idx, ticket in enumerate(strip):
        if not isinstance(ticket, list) or len(ticket) != 3:
            return False, f"ticket {t_idx}: not 3 rows"
        for r in range(3):
            if not isinstance(ticket[r], list) or len(ticket[r]) != 9:
                return False, f"ticket {t_idx}: row {r} not 9 cols"

        row_counts = [sum(1 for x in row if x) for row in ticket]
        if any(c != 5 for c in row_counts):
            return False, f"ticket {t_idx}: each row must have 5 numbers"

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

            for n in col_vals:
                if n in seen:
                    return False, f"duplicate number {n} in strip"
                seen.add(n)

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
    Balanced if max(block)-min(block) <= 2 across left/mid/right blocks.
    """
    left, mid, right = _ticket_block_counts(ticket)
    return (max(left, mid, right) - min(left, mid, right)) <= 2


def _alloc_is_balanced(alloc_row: List[int]) -> bool:
    """
    alloc_row length 9 sums to 15.
    """
    left = sum(alloc_row[0:3])
    mid = sum(alloc_row[3:6])
    right = sum(alloc_row[6:9])
    return (max(left, mid, right) - min(left, mid, right)) <= 2


def _block_index(col: int) -> int:
    return 0 if col <= 2 else (1 if col <= 5 else 2)


# ========================= GENERATION =========================

def _alloc_strip_col_counts() -> List[List[int]]:
    """
    Allocate per-column counts to 6 tickets.

    Returns A[6][9] such that:
      - A[t][c] in {1,2,3} (each ticket uses that column at least once)
      - For each column c, sum_t A[t][c] = STRIP_COL_TOTALS[c]
      - For each ticket t, sum_c A[t][c] = 15
      - Additionally: each ticket is balanced across left/middle/right blocks
        based on column totals (prevents heavy-left/heavy-right tickets).
    """
    TICKETS = 6
    COLS = 9
    target = STRIP_COL_TOTALS[:]
    A = [[0] * COLS for _ in range(TICKETS)]
    used_per_ticket = [0] * TICKETS

    # Track partial block totals while building (left/mid/right per ticket)
    block_used = [[0, 0, 0] for _ in range(TICKETS)]

    def compositions_of_total(total: int, k: int) -> List[List[int]]:
        result: List[List[int]] = []

        def rec(i: int, rem: int, cur: List[int]):
            if i == k:
                if rem == 0:
                    result.append(cur[:])
                return
            for x in (1, 2, 3):
                if x > rem:
                    continue
                rem_after = rem - x
                if rem_after < (k - i - 1) * 1:
                    continue
                if rem_after > (k - i - 1) * 3:
                    continue
                cur.append(x)
                rec(i + 1, rem_after, cur)
                cur.pop()

        rec(0, total, [])
        random.shuffle(result)
        return result

    possible_for_total = {tot: compositions_of_total(tot, TICKETS) for tot in set(target)}

    col_order = list(range(COLS))
    random.shuffle(col_order)

    def backtrack_col(idx: int) -> bool:
        if idx == COLS:
            return all(u == 15 for u in used_per_ticket) and all(_alloc_is_balanced(A[t]) for t in range(TICKETS))

        c = col_order[idx]
        need = target[c]
        candidates = possible_for_total[need]
        remaining_cols = COLS - idx - 1

        b = _block_index(c)

        for vec in candidates:
            ok = True

            # Capacity / feasibility check per ticket
            for t in range(TICKETS):
                new_used = used_per_ticket[t] + vec[t]
                if new_used > 15:
                    ok = False
                    break

                if remaining_cols > 0:
                    rem_need = 15 - new_used
                    min_possible = remaining_cols * 1
                    max_possible = remaining_cols * 3
                    if rem_need < min_possible or rem_need > max_possible:
                        ok = False
                        break
                else:
                    if new_used != 15:
                        ok = False
                        break

            if not ok:
                continue

            # Balance pruning (loose but effective):
            # if adding this column already makes the block gap > 2, reject early.
            for t in range(TICKETS):
                tmp_blocks = block_used[t][:]
                tmp_blocks[b] += vec[t]
                if (max(tmp_blocks) - min(tmp_blocks)) > 2:
                    ok = False
                    break

            if not ok:
                continue

            # Commit
            for t in range(TICKETS):
                A[t][c] = vec[t]
                used_per_ticket[t] += vec[t]
                block_used[t][b] += vec[t]

            if backtrack_col(idx + 1):
                return True

            # Rollback
            for t in range(TICKETS):
                used_per_ticket[t] -= vec[t]
                block_used[t][b] -= vec[t]
                A[t][c] = 0

        return False

    if not backtrack_col(0):
        raise ValueError("Failed to allocate strip column counts (balanced)")

    return A


def _mask_for_ticket(col_sums: List[int]) -> List[List[int]]:
    """
    Given per-column sums (each 1..3) for one ticket, create a 3x9 0/1 mask
    where each row sums to 5 and each column sums to the given number.

    Uses randomized order to avoid repeating patterns.
    """
    if len(col_sums) != 9:
        raise ValueError("col_sums must have length 9")
    if sum(col_sums) != 15:
        raise ValueError("sum(col_sums) must be 15 for a ticket")

    rows_left = [5, 5, 5]
    mask = [[0] * 9 for _ in range(3)]

    col_order = list(range(9))
    random.shuffle(col_order)

    def backtrack(idx: int) -> bool:
        if idx == 9:
            return rows_left == [0, 0, 0]

        c = col_order[idx]
        k = col_sums[c]

        valid_rows = [r for r in range(3) if rows_left[r] > 0]
        if len(valid_rows) < k:
            return False

        random.shuffle(valid_rows)
        combs = list(combinations(valid_rows, k))
        random.shuffle(combs)

        remaining_cols = 8 - idx

        for comb in combs:
            for r in comb:
                rows_left[r] -= 1
                mask[r][c] = 1

            feasible = True
            for r in range(3):
                if rows_left[r] < 0:
                    feasible = False
                    break
                if remaining_cols >= 0 and rows_left[r] > remaining_cols:
                    feasible = False
                    break

            if feasible and backtrack(idx + 1):
                return True

            for r in comb:
                rows_left[r] += 1
                mask[r][c] = 0

        return False

    if not backtrack(0):
        raise ValueError("Failed to build row mask for ticket")
    return mask


def generate_full_strip(max_attempts: int = 200) -> List[List[List[Optional[int]]]]:
    """
    Generate one full strip (6 tickets), fully valid per rules AND balanced.

    If no balanced strip is found within max_attempts, but at least one
    strictly valid strip was generated, that last valid strip is returned.
    """
    last_valid_strip: Optional[List[List[List[Optional[int]]]]] = None
    last_msg: str = "no_attempt"

    for _ in range(max_attempts):
        alloc = _alloc_strip_col_counts()  # balanced allocation by design

        pools: List[List[int]] = []
        for c in range(9):
            lo, hi = COL_RANGES[c]
            nums = list(range(lo, hi + 1))
            random.shuffle(nums)
            pools.append(nums[:STRIP_COL_TOTALS[c]])

        consumed = [0] * 9
        ticket_indices = list(range(6))
        random.shuffle(ticket_indices)

        try:
            tickets_tmp: List[Optional[List[List[Optional[int]]]]] = [None] * 6

            for t_pos in ticket_indices:
                col_sums = alloc[t_pos]
                mask = _mask_for_ticket(col_sums)

                ticket: List[List[Optional[int]]] = [[None] * 9 for _ in range(3)]

                for c in range(9):
                    need = col_sums[c]
                    take = pools[c][consumed[c]: consumed[c] + need]
                    consumed[c] += need
                    take.sort()

                    rows = [r for r in range(3) if mask[r][c] == 1]
                    for r, val in zip(rows, take):
                        ticket[r][c] = val

                tickets_tmp[t_pos] = ticket

            strip = [tickets_tmp[i] for i in range(6)]  # type: ignore

            ok, msg = validate_strip(strip)
            last_msg = msg
            if not ok:
                continue

            # Only store if truly valid (FIXED BUG)
            last_valid_strip = strip

            # Extra safety (should always pass now)
            if all(_is_balanced_ticket(t) for t in strip):
                return strip

        except Exception as e:
            last_msg = str(e)
            continue

    if last_valid_strip is not None:
        return last_valid_strip

    raise ValueError(f"Failed to generate balanced strip after {max_attempts} attempts: {last_msg}")
