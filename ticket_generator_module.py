# ticket_generator_module.py
import random
from typing import List, Optional, Tuple

# ----- Helpers -----
def _column_target_totals() -> List[int]:
    # per-column total numbers across a strip (6 tickets = 90 nums)
    # 1–9 : 9, 10–19 : 10, ... , 80–90 : 11
    return [9, 10, 10, 10, 10, 10, 10, 10, 11]

def _column_ranges() -> List[range]:
    return [
        range(1, 10),   # col 0
        range(10, 20),  # col 1
        range(20, 30),  # col 2
        range(30, 40),  # col 3
        range(40, 50),  # col 4
        range(50, 60),  # col 5
        range(60, 70),  # col 6
        range(70, 80),  # col 7
        range(80, 91),  # col 8
    ]

def _build_ticket_row_mask(col_counts: List[int]) -> List[List[int]]:
    """
    Given per-column counts for a single ticket (each 1 or 2; sum=15),
    assign them to rows so each row has exactly 5 cells.
    Returns a 3x9 mask of 0/1 (1 = place a number).
    Raises ValueError if fails.
    """
    # Start empty mask
    mask = [[0] * 9 for _ in range(3)]
    # remaining per row
    row_need = [5, 5, 5]  # 3 rows x 5 = 15

    # columns in random order so distribution varies
    cols = list(range(9))
    random.shuffle(cols)

    # First place “2” columns: put in the two rows with highest remaining needs
    two_cols = [c for c, k in enumerate(col_counts) if k == 2]
    random.shuffle(two_cols)
    for c in two_cols:
        # pick two rows with greatest remaining slots
        rows_sorted = sorted(range(3), key=lambda r: -row_need[r])
        placed = 0
        for r in rows_sorted:
            if row_need[r] > 0 and mask[r][c] == 0:
                mask[r][c] = 1
                row_need[r] -= 1
                placed += 1
                if placed == 2:
                    break
        if placed != 2:
            raise ValueError("Cannot place 2 in column")

    # Then place “1” columns
    one_cols = [c for c, k in enumerate(col_counts) if k == 1]
    random.shuffle(one_cols)
    for c in one_cols:
        # choose the row with the most remaining slots
        rows_sorted = sorted(range(3), key=lambda r: -row_need[r])
        placed = False
        for r in rows_sorted:
            if row_need[r] > 0 and mask[r][c] == 0:
                mask[r][c] = 1
                row_need[r] -= 1
                placed = True
                break
        if not placed:
            raise ValueError("Cannot place 1 in column")

    if any(x != 0 for x in row_need):
        raise ValueError("Row sums not satisfied")

    return mask

def _assign_strip_column_plan() -> List[List[int]]:
    """
    Create a 6x9 plan of 1/2 per ticket/column so:
      - every ticket has exactly 15 cells (sum per ticket across columns == 15)
      - every column across tickets sums to its target (e.g. 9,10,..,11)
      - each ticket/column is 1 or 2 (=> no blank columns)
    Returns list[ticket][col] = 1 or 2
    """
    targets = _column_target_totals()  # per column totals
    # baseline: every ticket gets 1 per column => each ticket has 9
    # extras needed per column:
    extras_per_col = [t - 6 for t in targets]  # 9->3, 10->4, 11->5
    # each ticket needs 6 extras (to go from 9 to 15)
    extras_remaining_per_ticket = [6] * 6

    # plan init to ones
    plan = [[1] * 9 for _ in range(6)]

    # we will assign extras (add +1) for columns
    # process columns in random order to vary strips
    cols_order = list(range(9))
    random.shuffle(cols_order)

    for c in cols_order:
        k = extras_per_col[c]  # how many "twos" we need in this column
        # choose k tickets that still need extras, prefer those with most remaining
        for _ in range(k):
            # eligible tickets are those who still can take an extra
            elig = [i for i in range(6) if extras_remaining_per_ticket[i] > 0]
            if not elig:
                # if we can't place, give up and retry entirely
                raise ValueError("No eligible ticket for extra")
            # pick the ticket with the most remaining extras (ties random)
            random.shuffle(elig)
            elig.sort(key=lambda i: -extras_remaining_per_ticket[i])
            t = elig[0]
            # place extra in column c for ticket t
            plan[t][c] = 2
            extras_remaining_per_ticket[t] -= 1

    if any(x != 0 for x in extras_remaining_per_ticket):
        raise ValueError("Extras not balanced among tickets")

    return plan  # 6 x 9 of 1 or 2

def _layout_for_ticket(col_counts: List[int]) -> List[List[int]]:
    # try a few times to map 1/2 per column into a row mask (3x9)
    for _ in range(50):
        try:
            return _build_ticket_row_mask(col_counts)
        except ValueError:
            continue
    raise ValueError("Failed to create row layout")

def _distribute_numbers_to_layouts(layouts: List[List[List[int]]]) -> List[List[List[Optional[int]]]]:
    """
    layouts: list of 6 items, each a 3x9 mask (0/1)
    Returns the 6 filled tickets with ascending numbers per column.
    """
    # prepare column pools (exact totals)
    col_ranges = _column_ranges()
    totals = _column_target_totals()
    pools = []
    for c in range(9):
        nums = list(col_ranges[c])
        # sample exactly totals[c] unique numbers from this column range
        chosen = random.sample(nums, totals[c])
        chosen.sort()
        pools.append(chosen)

    # Now assign numbers to each column, ticket by ticket, top-to-bottom
    tickets = [[[None for _ in range(9)] for __ in range(3)] for ___ in range(6)]

    for c in range(9):
        for t in range(6):
            # collect row indices where we need numbers for this ticket/col
            rows_here = [r for r in range(3) if layouts[t][r][c] == 1]
            rows_here.sort()  # ensure ascending top->bottom
            for r in rows_here:
                if not pools[c]:
                    raise ValueError("Ran out of numbers in column pool")
                tickets[t][r][c] = pools[c].pop(0)

    return tickets

# ----- Public API -----
def generate_full_strip() -> List[List[List[Optional[int]]]]:
    """
    Returns a list of 6 tickets (each 3x9 with ints or None).
    Rules:
      - Strip uses 1..90 exactly once
      - Each ticket: 15 numbers, 5 per row
      - Per ticket column count is 1 or 2 (no blank column)
      - Numbers ascending within each column
    """
    for _ in range(200):  # a few attempts in case of unlucky randomness
        try:
            # 1) column plan per ticket (6x9 of 1/2)
            plan = _assign_strip_column_plan()
            # 2) build per-ticket row layouts (3x9 masks)
            layouts = [_layout_for_ticket(plan[t]) for t in range(6)]
            # 3) fill numbers
            tickets = _distribute_numbers_to_layouts(layouts)
            return tickets
        except ValueError:
            continue
    raise ValueError("Failed to generate a valid strip after several attempts")

def validate_strip(strip: List[List[List[Optional[int]]]]) -> Tuple[bool, str]:
    """
    Quick validator for debugging.
    """
    if len(strip) != 6:
        return False, "Strip must have 6 tickets"
    seen = set()
    totals = [0]*9
    for t in strip:
        # shape
        if len(t) != 3 or any(len(r) != 9 for r in t):
            return False, "Ticket shape must be 3x9"
        # per row = 5
        for r in t:
            if sum(1 for v in r if v is not None) != 5:
                return False, "Each row must have exactly 5 numbers"
        # per column ascending, and count 1 or 2 (no blank col)
        for c in range(9):
            col_vals = [t[r][c] for r in range(3) if t[r][c] is not None]
            if not (1 <= len(col_vals) <= 2):
                return False, "Each column must have 1 or 2 numbers in a ticket"
            if col_vals != sorted(col_vals):
                return False, "Column not ascending"
    # strip-level: 1..90 exactly once, per column totals correct
    for c in range(9):
        rng = _column_ranges()[c]
        want = set(rng)
        got = []
        for t in strip:
            for r in range(3):
                v = t[r][c]
                if v is not None:
                    got.append(v)
        if len(got) != _column_target_totals()[c]:
            return False, f"Column {c} wrong total"
        if set(got) - set(rng):
            return False, f"Column {c} has out-of-range"
        totals[c] = len(got)
        seen.update(got)
    if seen != set(range(1,91)):
        return False, "Not all numbers 1..90 used exactly once"
    return True, "ok"
