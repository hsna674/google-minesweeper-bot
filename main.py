import pyautogui
import random
import time
from pynput import keyboard
import concurrent.futures
import argparse
import collections

parser = argparse.ArgumentParser(description="Minesweeper Bot Configuration")
parser.add_argument("--new", action="store_true", help="Start a new game")
parser.add_argument(
    "--ongoing", action="store_false", dest="new_game", help="Play an ongoing game"
)
parser.add_argument(
    "--debug", action="store_true", help="Save debug screenshots of the board"
)
parser.set_defaults(new_game=True)
args = parser.parse_args()

pyautogui.PAUSE = 0

left = 2580
top = 364
right = 3180
bottom = 864
cols = 24
rows = 20
hover_time = 0.1
kill_key = keyboard.Key.esc

width = right - left
height = bottom - top
tile_width = width // cols
tile_height = height // rows

color_map = {
    (231, 45, 23): 0,  # Flag
    (0, 108, 202): 1,  # 1
    (74, 140, 70): 2,  # 2
    (98, 145, 83): 2,  # 2
    (210, 57, 56): 3,  # 3
    (209, 42, 45): 3,  # 3
    (113, 33, 150): 4,  # 4
    (242, 159, 79): 5,  # 5
    (220, 167, 118): 5,  # 5
    (61, 156, 153): 6,  # 6
    (159, 208, 78): 99,  # Unopened tile
    (151, 202, 71): 99,  # Unopened tile
}

running = True

moves = -2


def capture_screenshot(capture_number=1):
    time.sleep(0.8)
    region = (left, top, width, height)
    screenshot = pyautogui.screenshot(region=region)
    if args.debug:
        screenshot.save(f"minesweeper_capture_{capture_number}.png")
    return screenshot


def generate_tile_coords():
    grid = []
    for row in range(rows):
        row_coords = []
        for col in range(cols):
            x = left + col * tile_width + tile_width // 2
            y = top + row * tile_height + tile_height // 2
            row_coords.append((x, y))
        grid.append(row_coords)
    return grid


def hover_tiles(grid):
    global running
    for row in grid:
        for x, y in row:
            if not running:
                print("Stopped by user.")
                return
            pyautogui.moveTo(x, y, duration=0.05)
            time.sleep(hover_time)


def on_press(key):
    global running
    if key == kill_key:
        print("Kill key pressed. Exiting...")
        running = False
        return False


def click_random_center_tile(tile_grid, center_radius=3, delay=0.15):
    rows = len(tile_grid)
    cols = len(tile_grid[0])

    center_row = rows // 2
    center_col = cols // 2

    row = random.randint(center_row - center_radius, center_row + center_radius)
    col = random.randint(center_col - center_radius, center_col + center_radius)

    left_click_tile(tile_grid, row, col)
    left_click_tile(tile_grid, row, col)


def extract_tile(board_image, row, col, tile_width, tile_height):
    left = col * tile_width
    top = row * tile_height
    right = left + tile_width
    bottom = top + tile_height

    tile_image = board_image.crop((left, top, right, bottom))
    return tile_image


def detect_tile_number(tile_img, color_map, scan_box=25):
    tile_img = tile_img.convert("RGB")
    w, h = tile_img.size
    offset_x = (w - scan_box) // 2
    offset_y = (h - scan_box) // 2

    plain_count = 0

    for x in range(offset_x, offset_x + scan_box):
        for y in range(offset_y, offset_y + scan_box):
            pixel = tile_img.getpixel((x, y))
            if pixel in color_map:
                if color_map[pixel] != 99:
                    return color_map[pixel]
                else:
                    plain_count += 1

    if plain_count == 625:
        return 99

    return -1  # Opened tile


def get_neighbors(row, col, board):
    neighbors = []
    rows = len(board)
    cols = len(board[0])

    for dr in [-1, 0, 1]:
        for dc in [-1, 0, 1]:
            if dr == 0 and dc == 0:
                continue  # Skip the tile itself
            r = row + dr
            c = col + dc
            if 0 <= r < rows and 0 <= c < cols:
                neighbors.append((r, c))
    return neighbors


def get_unopened_neighbors(row, col, board):
    unopened = []
    neighbors = get_neighbors(row, col, board)

    for r, c in neighbors:
        if board[r][c] == 99 or board[r][c] == 0:
            unopened.append((r, c))

    return unopened


def print_board(board):
    for row in board:
        print(" ".join(f"{val:2}" for val in row).replace("0", "F"))
    print()


def right_click_tile(tile_grid, row, col):
    global moves
    x, y = tile_grid[row][col]
    moves += 1
    pyautogui.click(x, y, button="right", duration=0)


def left_click_tile(tile_grid, row, col):
    global moves
    x, y = tile_grid[row][col]
    moves += 1
    pyautogui.click(x, y, button="left", duration=0)


def get_board_from_screenshot(screenshot, prev_hashes, cached_board):
    current_board = [[None] * cols for _ in range(rows)]
    tasks = []

    with concurrent.futures.ThreadPoolExecutor() as executor:
        for row in range(rows):
            for col in range(cols):
                args = (
                    row,
                    col,
                    screenshot,
                    tile_width,
                    tile_height,
                    prev_hashes[row][col],
                    cached_board[row][col],
                    color_map,
                )
                tasks.append(executor.submit(process_tile, args))

        for future in concurrent.futures.as_completed(tasks):
            row, col, value, new_hash = future.result()
            current_board[row][col] = value
            prev_hashes[row][col] = new_hash
            cached_board[row][col] = value

    return current_board


def process_board(board_state, tile_grid):
    flags = []
    to_click = []

    for row in range(rows):
        for col in range(cols):
            val = board_state[row][col]
            if 1 <= val <= 8:
                unopened_neighbors = get_unopened_neighbors(row, col, board_state)
                if val == len(unopened_neighbors):
                    for r, c in unopened_neighbors:
                        flags.append((r, c))

    flags = list(set(flags))
    made_flag = False
    for r, c in flags:
        if board_state[r][c] != 0:
            board_state[r][c] = 0
            right_click_tile(tile_grid, r, c)
            made_flag = True

    for row in range(rows):
        for col in range(cols):
            val = board_state[row][col]
            if 1 <= val <= 8:
                neighbors = get_neighbors(row, col, board_state)
                flag_count = sum(1 for r, c in neighbors if board_state[r][c] == 0)
                if val == flag_count:
                    for r, c in neighbors:
                        if board_state[r][c] == 99:
                            to_click.append((r, c))

    to_click = list(set(to_click))
    made_click = False
    for r, c in to_click:
        board_state[r][c] = -2
        left_click_tile(tile_grid, r, c)
        made_click = True

    return made_flag or made_click


def guess_least_risky_tile(board):
    prob_map = {}

    for row in range(rows):
        for col in range(cols):
            val = board[row][col]
            if 1 <= val <= 8:
                neighbors = get_neighbors(row, col, board)
                unopened = [(r, c) for r, c in neighbors if board[r][c] == 99]
                flagged = [(r, c) for r, c in neighbors if board[r][c] == 0]
                remaining = val - len(flagged)
                if remaining > 0 and unopened:
                    prob = remaining / len(unopened)
                    for r, c in unopened:
                        if (r, c) not in prob_map:
                            prob_map[(r, c)] = []
                        prob_map[(r, c)].append(prob)

    averaged_probs = {}
    for tile, probs in prob_map.items():
        averaged_probs[tile] = sum(probs) / len(probs)

    if averaged_probs:
        best_tile = min(averaged_probs.items(), key=lambda x: x[1])[0]
        return best_tile

    all_unopened = [
        (r, c) for r in range(rows) for c in range(cols) if board[r][c] == 99
    ]
    if all_unopened:
        return random.choice(all_unopened)

    return None


def find_connected_components(variables, constraints):
    if not variables:
        return []

    adj = collections.defaultdict(list)
    for var_tuple, _ in constraints:
        for i in range(len(var_tuple)):
            for j in range(i + 1, len(var_tuple)):
                u, v = var_tuple[i], var_tuple[j]
                adj[u].append(v)
                adj[v].append(u)

    components = []
    visited = set()
    for var in variables:
        if var not in visited:
            component_vars = set()
            q = collections.deque([var])
            visited.add(var)
            while q:
                current_var = q.popleft()
                component_vars.add(current_var)
                if current_var in adj:
                    for neighbor in adj[current_var]:
                        if neighbor not in visited:
                            visited.add(neighbor)
                            q.append(neighbor)

            component_constraints = []
            for constraint_vars, required_mines in constraints:
                if any(v in component_vars for v in constraint_vars):
                    component_constraints.append((constraint_vars, required_mines))

            final_component_vars = sorted(list(component_vars))
            components.append((final_component_vars, component_constraints))

    print(f"Split problem into {len(components)} independent component(s).")
    return components


def collect_constraints(board):
    unopened_neighbors_of_numbers = set()
    constraints = []
    variable_counts = collections.defaultdict(int)

    for r in range(rows):
        for c in range(cols):
            val = board[r][c]
            if 1 <= val <= 8:
                neighbors = get_neighbors(r, c, board)
                unopened_in_constraint = []
                flagged_count = 0

                for nr, nc in neighbors:
                    if board[nr][nc] == 99:
                        unopened_in_constraint.append((nr, nc))
                        unopened_neighbors_of_numbers.add((nr, nc))
                    elif board[nr][nc] == 0:
                        flagged_count += 1

                if unopened_in_constraint:
                    constraint_vars = tuple(sorted(unopened_in_constraint))
                    required_mines = val - flagged_count
                    constraints.append((constraint_vars, required_mines))
                    for var in constraint_vars:
                        variable_counts[var] += 1

    variables = sorted(list(unopened_neighbors_of_numbers))
    return variables, list(set(constraints)), variable_counts


def check_consistency(assignment, constraints):
    for var_tuple, required_mines in constraints:
        current_mines = 0
        unassigned_count = 0

        for r, c in var_tuple:
            if (r, c) in assignment:
                if assignment[(r, c)] == "mine":
                    current_mines += 1
            else:
                unassigned_count += 1

        if current_mines > required_mines:
            return False

        if current_mines + unassigned_count < required_mines:
            return False

    return True


def backtracking_solver(variable_index, assignment, variables, constraints, solutions):
    if not check_consistency(assignment, constraints):
        return

    if variable_index == len(variables):
        solutions.append(assignment.copy())
        return

    current_variable = variables[variable_index]

    assignment[current_variable] = "mine"
    backtracking_solver(
        variable_index + 1, assignment, variables, constraints, solutions
    )
    if len(solutions) > 1000:
        return

    assignment[current_variable] = "safe"
    backtracking_solver(
        variable_index + 1, assignment, variables, constraints, solutions
    )
    if len(solutions) > 1000:
        return

    del assignment[current_variable]


def solve_constraints(variables, constraints, variable_counts):
    solutions = []
    assignment = {}

    sorted_variables = sorted(
        variables, key=lambda var: variable_counts.get(var, 0), reverse=True
    )

    if len(variables) > 50:
        print(f"CSP solver skipped on component: Too many variables ({len(variables)})")
        return []

    print(
        f"Running CSP solver on a component with {len(variables)} variables and {len(constraints)} constraints..."
    )
    backtracking_solver(0, assignment, sorted_variables, constraints, solutions)
    print(f"CSP solver found {len(solutions)} solution(s) for this component.")
    return solutions


def analyze_solutions(solutions, variables):
    if not solutions:
        return [], []

    guaranteed_safes = []
    guaranteed_mines = []

    if len(solutions) > 1000:
        print(
            "Warning: Analysis skipped as the number of solutions exceeded the limit."
        )
        return [], []

    for var in variables:
        if all(sol.get(var) == "safe" for sol in solutions):
            guaranteed_safes.append(var)
            continue

        if all(sol.get(var) == "mine" for sol in solutions):
            guaranteed_mines.append(var)

    return guaranteed_safes, guaranteed_mines


def process_tile(args):
    (
        row,
        col,
        screenshot,
        tile_width,
        tile_height,
        prev_hash,
        cached_value,
        color_map,
    ) = args
    tile_img = extract_tile(screenshot, row, col, tile_width, tile_height)
    tile_data = tile_img.tobytes()

    if prev_hash == tile_data:
        return row, col, cached_value, tile_data

    value = detect_tile_number(tile_img, color_map)
    return row, col, value, tile_data


def solve_constraints_concurrently(variables, constraints, variable_counts):
    components = find_connected_components(variables, constraints)

    all_safe_tiles = []
    all_mine_tiles = []

    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_to_component = {
            executor.submit(
                solve_constraints, comp_vars, comp_consts, variable_counts
            ): (comp_vars)
            for comp_vars, comp_consts in components
        }

        for future in concurrent.futures.as_completed(future_to_component):
            component_vars = future_to_component[future]
            try:
                solutions = future.result()
                if solutions:
                    safe_tiles, mine_tiles = analyze_solutions(
                        solutions, component_vars
                    )
                    all_safe_tiles.extend(safe_tiles)
                    all_mine_tiles.extend(mine_tiles)
            except Exception as exc:
                print(f"A component generated an exception: {exc}")
    return all_safe_tiles, all_mine_tiles


def get_effective_tile_info(r, c, board):
    if not (1 <= board[r][c] <= 8):
        return None, None

    val = board[r][c]
    neighbors = get_neighbors(r, c, board)

    flagged_count = 0
    unopened_neighbors = []

    for nr, nc in neighbors:
        if board[nr][nc] == 0:  # Flagged
            flagged_count += 1
        elif board[nr][nc] == 99:  # Unopened
            unopened_neighbors.append((nr, nc))

    effective_value = val - flagged_count
    return effective_value, set(unopened_neighbors)


def recognize_and_apply_patterns(board, tile_grid):
    made_move = False
    safes_to_click = set()
    mines_to_flag = set()

    for r1 in range(rows):
        for c1 in range(cols):
            val1 = board[r1][c1]
            if not (1 <= val1 <= 8):
                continue

            rem_mines1, unopened1 = get_effective_tile_info(r1, c1, board)
            if not unopened1:
                continue

            for r2, c2 in get_neighbors(r1, c1, board):
                val2 = board[r2][c2]
                if not (1 <= val2 <= 8):
                    continue

                rem_mines2, unopened2 = get_effective_tile_info(r2, c2, board)
                if not unopened2:
                    continue

                if unopened2.issubset(unopened1) and unopened1 != unopened2:
                    difference = unopened1 - unopened2
                    mine_diff = rem_mines1 - rem_mines2

                    if mine_diff == 0:
                        for tile in difference:
                            if board[tile[0]][tile[1]] == 99:
                                safes_to_click.add(tile)

                    if mine_diff == len(difference):
                        for tile in difference:
                            if board[tile[0]][tile[1]] == 99:
                                mines_to_flag.add(tile)

    if safes_to_click:
        print(f"Pattern Recognition found safe tiles: {safes_to_click}")
        for r, c in safes_to_click:
            if board[r][c] == 99:
                left_click_tile(tile_grid, r, c)
                board[r][c] = -2  # Mark as clicked
                made_move = True

    if mines_to_flag:
        print(f"Pattern Recognition found mines: {mines_to_flag}")
        for r, c in mines_to_flag:
            if board[r][c] == 99:
                right_click_tile(tile_grid, r, c)
                board[r][c] = 0  # Mark as flagged
                made_move = True

    return made_move


if __name__ == "__main__":
    print(
        "Starting Minesweeper bot in 3 sec... Press ESC to stop. (Do not move mouse during execution!)"
    )
    time.sleep(3)

    tile_grid = generate_tile_coords()

    previous_tile_hashes = [[None] * cols for _ in range(rows)]
    cached_board_state = [[None] * cols for _ in range(rows)]

    listener = keyboard.Listener(on_press=on_press)
    listener.daemon = True
    listener.start()

    if args.new_game:
        click_random_center_tile(tile_grid)

    time.sleep(0.5)

    move_number = 1
    while running:
        print(f"\n--- Move {move_number} ---")

        screenshot = capture_screenshot(move_number)

        board_state = get_board_from_screenshot(
            screenshot, previous_tile_hashes, cached_board_state
        )
        print_board(board_state)

        move_made = process_board(board_state, tile_grid)

        if not move_made:
            move_made = recognize_and_apply_patterns(board_state, tile_grid)

        if not move_made:
            print(
                "No deterministic or pattern-based moves found. Trying Constraint Satisfaction solver..."
            )
            variables, constraints, variable_counts = collect_constraints(board_state)

            if not variables:
                print("No constraints found for solver.")
            else:
                safe_tiles, mine_tiles = solve_constraints_concurrently(
                    variables, constraints, variable_counts
                )

                if safe_tiles:
                    print(f"CSP found guaranteed safe tiles: {safe_tiles}")
                    for r, c in safe_tiles:
                        if board_state[r][c] == 99:
                            left_click_tile(tile_grid, r, c)
                            board_state[r][c] = -2
                            move_made = True

                if mine_tiles:
                    print(f"CSP found guaranteed mines: {mine_tiles}")
                    for r, c in mine_tiles:
                        if board_state[r][c] == 99:
                            right_click_tile(tile_grid, r, c)
                            board_state[r][c] = 0
                            move_made = True

        if not move_made:
            print(
                "No guaranteed moves found by any solver. Attempting least risky guess..."
            )
            guess_tile = guess_least_risky_tile(board_state)
            if guess_tile:
                r, c = guess_tile
                print(f"Guessing tile at ({r}, {c})")
                left_click_tile(tile_grid, r, c)
            else:
                all_unopened = [
                    (r, c)
                    for r in range(rows)
                    for c in range(cols)
                    if board_state[r][c] == 99
                ]
                if not all_unopened:
                    print("Game appears to be won! Stopping.")
                else:
                    print("Could not determine a guess. Stopping.")
                break

        move_number += 1

    print(f"\nTotal Moves made: {moves}")
    print("Done.")
