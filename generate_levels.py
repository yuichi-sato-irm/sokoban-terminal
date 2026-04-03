#!/usr/bin/env python3
"""Sokoban level generator using reverse play method.

Generates 1000 solvable levels with increasing difficulty and saves to levels.json.
"""

import json
import random
import sys
from collections import deque
from copy import deepcopy

SEED = 42

# Directions: (dr, dc)
DIRS = [(0, 1), (0, -1), (1, 0), (-1, 0)]
DIR_NAMES = ["R", "L", "D", "U"]

# Difficulty tiers
TIERS = [
    # (start, end, rows, cols, min_boxes, max_boxes, min_walls, max_walls, min_moves, max_moves, label)
    (1, 50, 5, 5, 1, 1, 0, 1, 20, 50, "easy"),
    (51, 150, 5, 6, 1, 2, 0, 2, 30, 80, "easy"),
    (151, 300, 6, 6, 2, 2, 1, 3, 50, 120, "medium"),
    (301, 450, 6, 7, 2, 3, 1, 3, 80, 150, "medium"),
    (451, 600, 7, 7, 2, 3, 2, 4, 100, 200, "hard"),
    (601, 750, 7, 8, 3, 4, 2, 5, 150, 300, "hard"),
    (751, 900, 8, 8, 3, 4, 3, 6, 200, 400, "expert"),
    (901, 1000, 8, 9, 4, 5, 3, 7, 300, 500, "expert"),
]

# Path templates for fake directory paths
PATH_PREFIXES = [
    "~/projects/{name}/src",
    "~/services/{name}/lib",
    "~/data/{name}/scripts",
    "~/infra/{name}/config",
    "~/frontend/{name}/components",
    "~/backend/{name}/api",
    "~/tools/{name}/bin",
    "~/projects/{name}/core",
    "~/services/{name}/handlers",
    "~/data/{name}/pipeline",
    "~/infra/{name}/modules",
    "~/frontend/{name}/pages",
    "~/backend/{name}/routes",
    "~/tools/{name}/utils",
    "~/projects/{name}/tests",
    "~/services/{name}/workers",
]

PROJECT_NAMES = [
    "api", "auth", "billing", "cache", "deploy", "etl", "gateway", "hooks",
    "ingestion", "jobs", "kafka", "lambda", "metrics", "notifications",
    "orders", "payments", "queue", "redis", "search", "terraform", "users",
    "vault", "webhooks", "xray", "yarn", "zookeeper", "analytics", "cdn",
    "dns", "elasticsearch", "firewall", "grafana", "hadoop", "istio",
    "jenkins", "kubernetes", "logging", "mongodb", "nginx", "openapi",
    "prometheus", "rabbitmq", "s3", "traefik", "ubuntu", "consul",
    "docker", "envoy", "flux",
]


def get_tier(level_id):
    for start, end, rows, cols, min_b, max_b, min_w, max_w, min_m, max_m, label in TIERS:
        if start <= level_id <= end:
            return rows, cols, min_b, max_b, min_w, max_w, min_m, max_m, label
    raise ValueError(f"No tier for level {level_id}")


def generate_path(rng):
    template = rng.choice(PATH_PREFIXES)
    name = rng.choice(PROJECT_NAMES)
    return template.format(name=name)


def create_room(rows, cols, num_internal_walls, rng):
    """Create a room with walls on border and some internal walls."""
    grid = []
    for r in range(rows):
        row = []
        for c in range(cols):
            if r == 0 or r == rows - 1 or c == 0 or c == cols - 1:
                row.append("#")
            else:
                row.append(" ")
        grid.append(row)

    # Place internal walls
    interior = [(r, c) for r in range(1, rows - 1) for c in range(1, cols - 1)]
    rng.shuffle(interior)

    placed = 0
    for r, c in interior:
        if placed >= num_internal_walls:
            break
        grid[r][c] = "#"
        # Check connectivity of remaining floor
        if not is_connected(grid, rows, cols):
            grid[r][c] = " "
        else:
            placed += 1

    return grid


def is_connected(grid, rows, cols):
    """Check if all floor tiles are connected via BFS."""
    floors = []
    for r in range(rows):
        for c in range(cols):
            if grid[r][c] == " ":
                floors.append((r, c))
    if len(floors) <= 1:
        return True

    visited = set()
    q = deque([floors[0]])
    visited.add(floors[0])
    while q:
        r, c = q.popleft()
        for dr, dc in DIRS:
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols and (nr, nc) not in visited and grid[nr][nc] == " ":
                visited.add((nr, nc))
                q.append((nr, nc))
    return len(visited) == len(floors)


def get_floor_cells(grid, rows, cols):
    return [(r, c) for r in range(rows) for c in range(cols) if grid[r][c] == " "]


def reverse_play(grid, rows, cols, targets, boxes, player, num_reverse_moves, rng):
    """Perform reverse moves from solved state.

    Returns (new_boxes, new_player, solution_directions) or None on failure.
    """
    boxes = set(boxes)
    pr, pc = player
    moves = []  # list of (direction_index, was_pull)

    for _ in range(num_reverse_moves):
        options = []

        for di, (dr, dc) in enumerate(DIRS):
            # Reverse walk: player moves to player + D (must be empty floor)
            nr, nc = pr + dr, pc + dc
            if (0 <= nr < rows and 0 <= nc < cols
                    and grid[nr][nc] == " " and (nr, nc) not in boxes):
                options.append(("walk", di, nr, nc, None, None))

            # Reverse pull: box is at player + D, player moves to player - D
            # Box moves from player+D to player's old pos
            br, bc = pr + dr, pc + dc  # box current pos
            nr2, nc2 = pr - dr, pc - dc  # player new pos
            if (0 <= br < rows and 0 <= bc < cols
                    and 0 <= nr2 < rows and 0 <= nc2 < cols
                    and (br, bc) in boxes
                    and grid[nr2][nc2] == " "
                    and (nr2, nc2) not in boxes):
                options.append(("pull", di, nr2, nc2, br, bc))

        if not options:
            break

        choice = rng.choice(options)
        if choice[0] == "walk":
            _, di, nr, nc, _, _ = choice
            moves.append((di, False))
            pr, pc = nr, nc
        else:
            _, di, nr, nc, br, bc = choice
            moves.append((di, True))
            # Box moves from (br, bc) to old player pos
            boxes.remove((br, bc))
            boxes.add((pr, pc))
            pr, pc = nr, nc

    return boxes, (pr, pc), moves


def moves_to_solution(moves):
    """Convert reverse moves to forward solution.

    Forward solution is the reverse sequence with corrected directions:
    - Reverse walk with dir D: player went P -> P+D. Forward: P+D -> P, direction = -D.
    - Reverse pull with dir D: player went P -> P-D, box P+D -> P.
      Forward: player at P-D moves to P (direction +D), pushing box from P to P+D.
    """
    opposite = {0: 1, 1: 0, 2: 3, 3: 2}  # R<->L, D<->U
    solution = []
    for di, was_pull in reversed(moves):
        if was_pull:
            solution.append(di)  # forward push in same direction
        else:
            solution.append(opposite[di])  # forward walk in opposite direction
    return solution


def simulate_solution(grid, rows, cols, targets, initial_boxes, initial_player, solution):
    """Replay solution and check if it reaches solved state.

    Returns True if all boxes end up on targets.
    """
    boxes = set(initial_boxes)
    pr, pc = initial_player

    for di in solution:
        dr, dc = DIRS[di]
        nr, nc = pr + dr, pc + dc

        if not (0 <= nr < rows and 0 <= nc < cols):
            return False
        if grid[nr][nc] == "#":
            return False

        if (nr, nc) in boxes:
            # Push
            bnr, bnc = nr + dr, nc + dc
            if not (0 <= bnr < rows and 0 <= bnc < cols):
                return False
            if grid[bnr][bnc] == "#" or (bnr, bnc) in boxes:
                return False
            boxes.remove((nr, nc))
            boxes.add((bnr, bnc))

        pr, pc = nr, nc

    return boxes == set(targets)


def build_map(grid, rows, cols, targets, boxes, player):
    """Build map strings from grid state."""
    display = [row[:] for row in grid]
    target_set = set(targets)
    box_set = set(boxes)

    for r, c in targets:
        if display[r][c] == " ":
            display[r][c] = "."

    for r, c in boxes:
        if (r, c) in target_set:
            display[r][c] = "*"
        else:
            display[r][c] = "$"

    pr, pc = player
    if (pr, pc) in target_set:
        display[pr][pc] = "+"
    else:
        display[pr][pc] = "@"

    # Convert to strings, strip trailing spaces
    result = []
    for row in display:
        line = "".join(row).rstrip()
        result.append(line)

    return result


def generate_level(level_id, rng):
    """Generate a single solvable level. Returns level dict or None."""
    rows, cols, min_b, max_b, min_w, max_w, min_moves, max_moves, label = get_tier(level_id)
    num_boxes = rng.randint(min_b, max_b)
    num_walls = rng.randint(min_w, max_w)
    num_reverse = rng.randint(min_moves, max_moves)

    # Create room
    grid = create_room(rows, cols, num_walls, rng)
    floors = get_floor_cells(grid, rows, cols)

    if len(floors) < num_boxes + 1:
        return None

    # Place targets and boxes (solved state: boxes on targets)
    rng.shuffle(floors)
    targets = [floors[i] for i in range(num_boxes)]
    boxes = list(targets)  # boxes start on targets
    player_pos = floors[num_boxes]

    # Reverse play
    result = reverse_play(grid, rows, cols, targets, boxes, player_pos, num_reverse, rng)
    if result is None:
        return None

    final_boxes, final_player, reverse_moves = result

    # Accept if we got at least 60% of desired moves (small grids may not allow more)
    if len(reverse_moves) < max(5, min_moves // 3):
        return None

    # Check no box is on a target (puzzle shouldn't be partially solved)
    target_set = set(targets)
    for b in final_boxes:
        if b in target_set:
            return None

    # Build forward solution
    solution = moves_to_solution(reverse_moves)

    # Verify solution
    if not simulate_solution(grid, rows, cols, targets, final_boxes, final_player, solution):
        return None

    # Build map
    map_lines = build_map(grid, rows, cols, targets, final_boxes, final_player)
    path = generate_path(rng)

    return {
        "id": level_id,
        "path": path,
        "map": map_lines,
        "difficulty": label,
        "solution_length": len(solution),
        "num_boxes": num_boxes,
    }


def main():
    rng = random.Random(SEED)
    levels = []
    max_attempts = 100

    for level_id in range(1, 1001):
        generated = False
        for attempt in range(max_attempts):
            level = generate_level(level_id, rng)
            if level is not None:
                levels.append(level)
                generated = True
                break

        if not generated:
            print(f"FAILED to generate level {level_id} after {max_attempts} attempts", file=sys.stderr)
            sys.exit(1)

        if level_id % 100 == 0:
            print(f"Generated {level_id}/1000 levels")

    # Verification pass
    print("\nVerifying all levels...")
    failures = 0
    for level in levels:
        lid = level["id"]
        map_lines = level["map"]
        rows = len(map_lines)
        cols = max(len(line) for line in map_lines)

        # Parse map
        grid = []
        targets = []
        boxes = []
        player = None
        for r, line in enumerate(map_lines):
            row = []
            for c in range(cols):
                ch = line[c] if c < len(line) else " "
                if ch == "#":
                    row.append("#")
                elif ch == " ":
                    row.append(" ")
                elif ch == ".":
                    row.append(" ")
                    targets.append((r, c))
                elif ch == "$":
                    row.append(" ")
                    boxes.append((r, c))
                elif ch == "@":
                    row.append(" ")
                    player = (r, c)
                elif ch == "+":
                    row.append(" ")
                    player = (r, c)
                    targets.append((r, c))
                elif ch == "*":
                    row.append(" ")
                    targets.append((r, c))
                    boxes.append((r, c))
                else:
                    row.append(" ")
            grid.append(row)

        # Check box count == target count
        if len(boxes) != len(targets):
            print(f"  Level {lid}: box count ({len(boxes)}) != target count ({len(targets)})")
            failures += 1
            continue

        if len(boxes) != level["num_boxes"]:
            print(f"  Level {lid}: num_boxes mismatch")
            failures += 1

    # Summary
    diff_counts = {}
    for level in levels:
        d = level["difficulty"]
        diff_counts[d] = diff_counts.get(d, 0) + 1

    print(f"\nSummary:")
    print(f"  Total levels: {len(levels)}")
    for d in ["easy", "medium", "hard", "expert"]:
        print(f"  {d}: {diff_counts.get(d, 0)}")
    print(f"  Verification failures: {failures}")

    # Save
    output = {"levels": levels}
    with open("/Users/ysato/sandbox/console-game/levels.json", "w") as f:
        json.dump(output, f, separators=(",", ":"))

    print(f"\nSaved to levels.json ({len(levels)} levels)")


if __name__ == "__main__":
    main()
