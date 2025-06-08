import random
from typing import List, Optional

def generate_full_strip() -> List[List[List[Optional[int]]]]:
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

    max_per_column = {0: 9, 8: 11}
    for c in range(1, 8):
        max_per_column[c] = 10

    for attempt in range(500):
        try:
            col_usage = [0] * 9
            layouts = []

            for _ in range(6):
                for layout_attempt in range(1000):
                    layout = [[0 for _ in range(9)] for _ in range(3)]
                    row_counts = [0] * 3
                    col_counts = [0] * 9
                    temp_col_usage = [0] * 9
                    filled = 0

                    for col in random.sample(range(9), 9):
                        possible_rows = [r for r in range(3) if row_counts[r] < 5 and col_counts[col] < 3]
                        if not possible_rows or col_usage[col] + temp_col_usage[col] >= max_per_column[col]:
                            break
                        row = random.choice(possible_rows)
                        layout[row][col] = 1
                        row_counts[row] += 1
                        col_counts[col] += 1
                        temp_col_usage[col] += 1
                        filled += 1
                    else:
                        tries = 0
                        while filled < 15 and tries < 3000:
                            possible_cells = [
                                (r, c)
                                for r in range(3) for c in range(9)
                                if layout[r][c] == 0 and
                                   row_counts[r] < 5 and
                                   col_counts[c] < 3 and
                                   col_usage[c] + temp_col_usage[c] < max_per_column[c]
                            ]
                            if not possible_cells:
                                break
                            r, c = random.choice(possible_cells)
                            layout[r][c] = 1
                            row_counts[r] += 1
                            col_counts[c] += 1
                            temp_col_usage[c] += 1
                            filled += 1
                            tries += 1

                        if filled == 15 and all(rc == 5 for rc in row_counts):
                            for c in range(9):
                                col_usage[c] += temp_col_usage[c]
                            layouts.append(layout)
                            break
                else:
                    raise ValueError("Ticket layout failed")

            column_numbers = {
                c: random.sample(COLUMN_RANGES[c], max_per_column[c])
                for c in range(9)
            }

            strip = []
            for layout in layouts:
                ticket = [[None for _ in range(9)] for _ in range(3)]
                for col in range(9):
                    positions = [(r, col) for r in range(3) if layout[r][col] == 1]
                    for r, c in positions:
                        ticket[r][c] = column_numbers[c].pop()
                ticket = sort_ticket_columns(ticket)  # Ensure top-down sorting
                strip.append(ticket)

            return strip
        except Exception:
            continue

    raise ValueError("Failed to generate valid strip after many attempts")


def sort_ticket_columns(ticket: List[List[Optional[int]]]) -> List[List[Optional[int]]]:
    """
    Sorts each column of a Housie90 ticket in ascending order (top to bottom),
    preserving blank cells (None).
    """
    transposed = list(map(list, zip(*ticket)))  # Columns

    for i, col in enumerate(transposed):
        # Extract only numbers with their row indices
        numbered_cells = [(idx, val) for idx, val in enumerate(col) if val is not None]
        sorted_values = sorted(val for _, val in numbered_cells)
        sorted_col = [None] * 3
        for (idx, _), val in zip(numbered_cells, sorted_values):
            sorted_col[idx] = val
        transposed[i] = sorted_col

    # Return to row-wise layout
    return list(map(list, zip(*transposed)))


def get_column(number: int) -> int:
    if 1 <= number <= 9:
        return 0
    elif 10 <= number <= 19:
        return 1
    elif 20 <= number <= 29:
        return 2
    elif 30 <= number <= 39:
        return 3
    elif 40 <= number <= 49:
        return 4
    elif 50 <= number <= 59:
        return 5
    elif 60 <= number <= 69:
        return 6
    elif 70 <= number <= 79:
        return 7
    elif 80 <= number <= 90:
        return 8
    else:
        raise ValueError("Number out of range")
