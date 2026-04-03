#!/usr/bin/env python3
"""BFS Sokoban solver for all levels in escape.py."""

import sys
from collections import deque

# Import levels from escape.py
sys.path.insert(0, "/Users/ysato/sandbox/console-game")
from escape import LEVELS


def parse_level(level_data):
    """Parse a level map into grid, player position, box positions, and target positions."""
    raw = level_data["map"]
    max_w = max(len(row) for row in raw)
    grid = [row.ljust(max_w) for row in raw]

    player = None
    boxes = set()
    targets = set()

    for r, row in enumerate(grid):
        for c, ch in enumerate(row):
            if ch == "@":
                player = (r, c)
            elif ch == "+":
                player = (r, c)
                targets.add((r, c))
            elif ch == "$":
                boxes.add((r, c))
            elif ch == ".":
                targets.add((r, c))
            elif ch == "*":
                boxes.add((r, c))
                targets.add((r, c))

    return grid, player, frozenset(boxes), frozenset(targets)


def get_walls(grid):
    """Extract wall positions as a frozenset."""
    walls = set()
    for r, row in enumerate(grid):
        for c, ch in enumerate(row):
            if ch == "#":
                walls.add((r, c))
    return frozenset(walls)


def find_simple_deadlocks(grid, walls, targets):
    """Find all floor positions where a box would be in a dead corner (not on a target)."""
    rows = len(grid)
    cols = len(grid[0])
    deadlocks = set()

    for r in range(rows):
        for c in range(cols):
            if (r, c) in walls or (r, c) in targets:
                continue
            if grid[r][c] == "#":
                continue
            # Check if this is a corner: wall on two adjacent sides (forming an L)
            up = (r - 1, c) in walls or r - 1 < 0
            down = (r + 1, c) in walls or r + 1 >= rows
            left = (r, c - 1) in walls or c - 1 < 0
            right = (r, c + 1) in walls or c + 1 >= cols

            if (up and left) or (up and right) or (down and left) or (down and right):
                deadlocks.add((r, c))

    return deadlocks


def solve_bfs(level_data, level_num):
    """Solve a Sokoban level using BFS. Returns (solvable, moves, pushes) or (False, 0, 0)."""
    grid, player, boxes, targets = parse_level(level_data)
    walls = get_walls(grid)
    deadlocks = find_simple_deadlocks(grid, walls, targets)
    rows = len(grid)
    cols = len(grid[0])

    if len(boxes) != len(targets):
        return False, 0, 0, f"Box/target mismatch: {len(boxes)} boxes, {len(targets)} targets"

    # State: (player_pos, frozenset_of_boxes)
    initial_state = (player, boxes)

    if boxes == targets:
        return True, 0, 0, "Already solved"

    # BFS
    queue = deque()
    queue.append((player, boxes, 0, 0))  # player, boxes, moves, pushes
    visited = {(player, boxes)}

    directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]

    iterations = 0
    max_iterations = 5_000_000

    while queue and iterations < max_iterations:
        iterations += 1
        p, bxs, moves, pushes = queue.popleft()
        pr, pc = p

        for dr, dc in directions:
            nr, nc = pr + dr, pc + dc

            # Out of bounds or wall
            if nr < 0 or nr >= rows or nc < 0 or nc >= cols:
                continue
            if (nr, nc) in walls:
                continue

            new_boxes = bxs
            new_pushes = pushes

            if (nr, nc) in bxs:
                # Pushing a box
                bnr, bnc = nr + dr, nc + dc
                if bnr < 0 or bnr >= rows or bnc < 0 or bnc >= cols:
                    continue
                if (bnr, bnc) in walls or (bnr, bnc) in bxs:
                    continue
                # Deadlock check
                if (bnr, bnc) in deadlocks:
                    continue
                new_boxes = bxs - {(nr, nc)} | {(bnr, bnc)}
                new_pushes = pushes + 1

            state = ((nr, nc), new_boxes)
            if state in visited:
                continue
            visited.add(state)

            if new_boxes == targets:
                return True, moves + 1, new_pushes, f"Explored {iterations} states, visited {len(visited)}"

            queue.append(((nr, nc), new_boxes, moves + 1, new_pushes))

    if iterations >= max_iterations:
        return False, 0, 0, f"Hit iteration limit ({max_iterations}), visited {len(visited)} states"
    return False, 0, 0, f"No solution found, visited {len(visited)} states"


def main():
    print(f"Sokoban Solver - {len(LEVELS)} levels")
    print("=" * 60)

    all_solvable = True

    for i, level in enumerate(LEVELS):
        # Validate box/target counts
        raw = level["map"]
        max_w = max(len(row) for row in raw)
        grid = [row.ljust(max_w) for row in raw]

        box_count = sum(row.count("$") + row.count("*") for row in grid)
        target_count = sum(row.count(".") + row.count("+") + row.count("*") for row in grid)

        status = "OK" if box_count == target_count else "MISMATCH"
        print(f"\nLevel {i+1:2d} ({level['path']:<35s}) boxes={box_count} targets={target_count} [{status}]")

        if box_count != target_count:
            print(f"  ERROR: Box/target count mismatch!")
            all_solvable = False
            continue

        solvable, moves, pushes, info = solve_bfs(level, i)

        if solvable:
            print(f"  SOLVABLE - {moves} moves, {pushes} pushes ({info})")
        else:
            print(f"  UNSOLVABLE - {info}")
            all_solvable = False

    print("\n" + "=" * 60)
    if all_solvable:
        print("ALL 20 LEVELS ARE SOLVABLE")
    else:
        print("SOME LEVELS ARE UNSOLVABLE - SEE ABOVE")


if __name__ == "__main__":
    main()
