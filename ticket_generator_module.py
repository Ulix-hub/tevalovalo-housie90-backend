import random

def generate_ticket():
    ticket = [[0 for _ in range(9)] for _ in range(3)]
    
    # Define column ranges
    columns = []
    for i in range(9):
        start = i * 10 + 1
        end = start + 9
        if i == 0:
            start = 1
            end = 9
        elif i == 8:
            end = 91
        columns.append(list(range(start, end)))

    # Shuffle column numbers
    for col in columns:
        random.shuffle(col)

    # Step 1: Assign 15 numbers (5 per row, 15 per ticket)
    positions = [set() for _ in range(3)]
    filled = set()
    while sum(len(r) for r in positions) < 15:
        row = random.choice(range(3))
        col = random.choice(range(9))
        if len(positions[row]) < 5 and col not in positions[row] and (row, col) not in filled:
            positions[row].add(col)
            filled.add((row, col))

    # Step 2: Fill ticket grid
    col_counts = [0]*9
    for row in range(3):
        for col in sorted(positions[row]):
            while True:
                num = columns[col].pop()
                if col_counts[col] < 3:
                    ticket[row][col] = num
                    col_counts[col] += 1
                    break

    return ticket

def generate_full_strip():
    return [generate_ticket() for _ in range(6)]
