
import random

def generate_ticket():
    ticket = [[0]*9 for _ in range(3)]
    columns = [list(range(i*10+1, i*10+11)) for i in range(9)]
    columns[0] = list(range(1, 10))
    columns[-1] = list(range(80, 91))
    for col in columns:
        random.shuffle(col)

    filled_columns = random.sample(range(9), 5)
    for row in range(3):
        used_cols = random.sample(range(9), 5)
        used_cols.sort()
        for col in used_cols:
            if columns[col]:
                ticket[row][col] = columns[col].pop()
    return ticket

def generate_full_strip():
    return [generate_ticket() for _ in range(6)]
