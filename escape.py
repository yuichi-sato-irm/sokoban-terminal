#!/usr/bin/env python3
"""
dirclean v2.0.0 — Directory Cleanup Tool
Organize misplaced files into their correct locations.
(Actually: Sokoban)
"""

import sys
import os
import tty
import termios
import copy
import time
import json
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent
LEVELS_FILE = BASE_DIR / "levels.json"
SCORE_FILE = BASE_DIR / ".dirclean_scores.json"
SAVE_FILE = BASE_DIR / ".dirclean_save.json"

# ── Colors ─────────────────────────────────────────────────────

RESET = "\033[0m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
CYAN = "\033[36m"
DIM = "\033[2m"
BOLD = "\033[1m"
WHITE = "\033[37m"

# ── Level loading ─────────────────────────────────────────────

def load_levels():
    if not LEVELS_FILE.exists():
        print(f"{RED}Error: {LEVELS_FILE} not found.{RESET}")
        print(f"{DIM}Run 'python3 generate_levels.py' to generate levels.{RESET}")
        sys.exit(1)
    data = json.loads(LEVELS_FILE.read_text())
    return data["levels"]


LEVELS = load_levels()

# ── Tile rendering ─────────────────────────────────────────────

TILE_WALL = f"{DIM}░░{RESET}"
TILE_FLOOR = "  "
TILE_PLAYER = f"{CYAN}{BOLD}>>{RESET}"
TILE_BOX = f"{YELLOW}[]{RESET}"
TILE_TARGET = f"{GREEN}{DIM}··{RESET}"
TILE_BOX_ON = f"{GREEN}{BOLD}[]{RESET}"
TILE_PLAYER_ON = f"{CYAN}{BOLD}>>{RESET}"


def render_tile(ch):
    return {
        "#": TILE_WALL,
        " ": TILE_FLOOR,
        "@": TILE_PLAYER,
        "$": TILE_BOX,
        ".": TILE_TARGET,
        "*": TILE_BOX_ON,
        "+": TILE_PLAYER_ON,
    }.get(ch, "  ")


# ── Scoring ────────────────────────────────────────────────────


def calc_score(moves, pushes, elapsed, num_targets):
    base = moves + pushes * 2
    time_limit = num_targets * 60
    time_penalty = max(0, int((elapsed - time_limit) / 10))
    return base + time_penalty


def calc_rank(score, num_targets):
    ratio = score / max(num_targets, 1)
    if ratio <= 5:
        return "S"
    elif ratio <= 10:
        return "A"
    elif ratio <= 20:
        return "B"
    elif ratio <= 35:
        return "C"
    else:
        return "D"


RANK_COLORS = {
    "S": f"{YELLOW}{BOLD}",
    "A": f"{GREEN}{BOLD}",
    "B": f"{CYAN}",
    "C": f"{WHITE}",
    "D": f"{DIM}",
    "-": f"{DIM}",
}


def load_scores():
    if SCORE_FILE.exists():
        try:
            return json.loads(SCORE_FILE.read_text())
        except Exception:
            return {}
    return {}


def save_scores(scores):
    SCORE_FILE.write_text(json.dumps(scores, indent=2, ensure_ascii=False))


def get_player_name():
    try:
        import subprocess
        result = subprocess.run(
            ["git", "config", "user.name"],
            capture_output=True, text=True, timeout=3,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    return os.environ.get("USER", "anonymous")


# ── Save / Load ───────────────────────────────────────────────


def save_game(game):
    data = {
        "current_level": game.level_num,
        "level_results": game.level_results,
        "skipped": list(game.skipped),
        "player": get_player_name(),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    SAVE_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def load_game():
    if not SAVE_FILE.exists():
        return None
    try:
        return json.loads(SAVE_FILE.read_text())
    except Exception:
        return None


def clear_save():
    if SAVE_FILE.exists():
        SAVE_FILE.unlink()
    if SCORE_FILE.exists():
        SCORE_FILE.unlink()


# ── Game logic ─────────────────────────────────────────────────


class Sokoban:
    def __init__(self):
        self.level_num = 0
        self.grid = []
        self.moves = 0
        self.pushes = 0
        self.history = []
        self.max_level = len(LEVELS)
        self.level_start_time = 0.0
        self.level_results = [None] * self.max_level
        self.skipped = set()

    def load_level(self, n):
        self.level_num = n
        raw = LEVELS[n]["map"]
        max_w = max(len(row) for row in raw)
        self.grid = [list(row.ljust(max_w)) for row in raw]
        self.moves = 0
        self.pushes = 0
        self.history = []
        self.level_start_time = time.time()

    def find_player(self):
        for r, row in enumerate(self.grid):
            for c, ch in enumerate(row):
                if ch in ("@", "+"):
                    return r, c
        return 0, 0

    def move(self, dr, dc):
        pr, pc = self.find_player()
        nr, nc = pr + dr, pc + dc
        nnr, nnc = pr + 2 * dr, pc + 2 * dc

        rows = len(self.grid)
        cols = len(self.grid[0])

        if nr < 0 or nr >= rows or nc < 0 or nc >= cols:
            return
        target = self.grid[nr][nc]

        if target == "#":
            return

        snapshot = (copy.deepcopy(self.grid), self.moves, self.pushes)

        if target in ("$", "*"):
            if nnr < 0 or nnr >= rows or nnc < 0 or nnc >= cols:
                return
            beyond = self.grid[nnr][nnc]
            if beyond in ("#", "$", "*"):
                return

            self.grid[nnr][nnc] = "*" if beyond == "." else "$"
            self.grid[nr][nc] = "+" if target == "*" else "@"
            self.grid[pr][pc] = "." if self.grid[pr][pc] == "+" else " "
            self.pushes += 1
        else:
            self.grid[nr][nc] = "+" if target == "." else "@"
            self.grid[pr][pc] = "." if self.grid[pr][pc] == "+" else " "

        self.moves += 1
        self.history.append(snapshot)

    def undo(self):
        if self.history:
            self.grid, self.moves, self.pushes = self.history.pop()

    def is_complete(self):
        for row in self.grid:
            for ch in row:
                if ch in (".", "+"):
                    return False
        return True

    def count_targets(self):
        total = 0
        done = 0
        for row in self.grid:
            for ch in row:
                if ch in (".", "+"):
                    total += 1
                elif ch == "*":
                    total += 1
                    done += 1
        return done, total

    def record_level(self):
        elapsed = time.time() - self.level_start_time
        _, total = self.count_targets()
        score = calc_score(self.moves, self.pushes, elapsed, total)
        rank = calc_rank(score, total)
        self.level_results[self.level_num] = {
            "level": self.level_num + 1,
            "path": LEVELS[self.level_num]["path"],
            "moves": self.moves,
            "pushes": self.pushes,
            "time": round(elapsed, 1),
            "score": score,
            "rank": rank,
            "skipped": False,
        }

    def record_skip(self):
        self.level_results[self.level_num] = {
            "level": self.level_num + 1,
            "path": LEVELS[self.level_num]["path"],
            "moves": 0,
            "pushes": 0,
            "time": 0,
            "score": 0,
            "rank": "-",
            "skipped": True,
        }
        self.skipped.add(self.level_num)

    def restore_from_save(self, save_data):
        self.level_num = save_data["current_level"]
        self.skipped = set(save_data.get("skipped", []))
        raw_results = save_data.get("level_results", [])
        for i, r in enumerate(raw_results):
            if r is not None and i < self.max_level:
                self.level_results[i] = r

    def solved_count(self):
        return sum(1 for r in self.level_results if r and not r["skipped"])

    def total_score(self):
        return sum(r["score"] for r in self.level_results if r and not r["skipped"])

    def total_time(self):
        return sum(r["time"] for r in self.level_results if r and not r["skipped"])


# ── Display ────────────────────────────────────────────────────


def fmt_time(seconds):
    m, s = divmod(int(seconds), 60)
    return f"{m}:{s:02d}"


def difficulty_label(level_idx):
    lv = LEVELS[level_idx]
    d = lv.get("difficulty", "")
    if d == "easy":
        return f"{GREEN}EASY{RESET}"
    elif d == "medium":
        return f"{YELLOW}MEDIUM{RESET}"
    elif d == "hard":
        return f"{RED}HARD{RESET}"
    elif d == "expert":
        return f"{RED}{BOLD}EXPERT{RESET}"
    else:
        return f"{DIM}---{RESET}"


def render(game):
    os.system("clear" if os.name != "nt" else "cls")
    lv = LEVELS[game.level_num]
    done, total = game.count_targets()
    elapsed = time.time() - game.level_start_time

    print(f"{BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}")
    print(f"{BOLD}  dirclean{RESET} {DIM}v2.0.0 — directory cleanup tool{RESET}")
    print(f"{BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}")
    print()
    print(
        f"  {DIM}Scanning:{RESET} {CYAN}{lv['path']}{RESET}"
        f"   {DIM}[{game.level_num + 1}/{game.max_level}]{RESET}"
        f"  {difficulty_label(game.level_num)}"
    )
    print()

    for row in game.grid:
        line = "    "
        for ch in row:
            line += render_tile(ch)
        print(line)
    print()

    bar_w = 20
    filled = int(bar_w * done / total) if total else 0
    bar = f"{GREEN}{'█' * filled}{RESET}{DIM}{'░' * (bar_w - filled)}{RESET}"
    print(
        f"  {DIM}Files:{RESET} {done}/{total} [{bar}]"
        f"  {DIM}Moves:{RESET} {game.moves}"
        f"  {DIM}Pushes:{RESET} {game.pushes}"
        f"  {DIM}Time:{RESET} {fmt_time(elapsed)}"
    )
    print()
    solved = game.solved_count()
    print(
        f"  {DIM}Progress:{RESET} {solved}/{game.max_level} cleaned"
        f"   {DIM}← ↑ ↓ → move  u undo  r reset  n skip  q quit{RESET}"
    )
    print()


def render_complete(game, result):
    render(game)
    rc = RANK_COLORS.get(result["rank"], "")
    print(f"  {GREEN}{BOLD}✓ Directory cleaned!{RESET}")
    print(
        f"  {DIM}Score:{RESET} {BOLD}{result['score']}{RESET}"
        f"  {DIM}Rank:{RESET} {rc}{result['rank']}{RESET}"
        f"  {DIM}Time:{RESET} {fmt_time(result['time'])}"
    )
    print(f"  {DIM}Press any key to continue...{RESET}")
    print()


def render_scorecard(game):
    os.system("clear" if os.name != "nt" else "cls")
    player = get_player_name()
    solved = game.solved_count()
    skipped = sum(1 for r in game.level_results if r and r["skipped"])

    print(f"{BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}")
    print(f"{BOLD}  dirclean{RESET} {DIM}— session report{RESET}")
    print(f"{BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}")
    print()
    print(
        f"  {DIM}User:{RESET} {CYAN}{player}{RESET}"
        f"   {DIM}Cleaned:{RESET} {solved}/{game.max_level}"
        f"   {DIM}Skipped:{RESET} {skipped}"
    )
    print()

    # Show recent 20 levels around current progress
    results_with_data = [
        i for i, r in enumerate(game.level_results) if r is not None
    ]
    if results_with_data:
        start = max(0, min(results_with_data) // 10 * 10)
        end = min(game.max_level, max(results_with_data) + 1)
        # limit to 20 rows
        if end - start > 20:
            start = max(0, end - 20)

        print(f"  {DIM}{'#':>4}  {'Directory':<34} {'Moves':>5} {'Push':>5} {'Time':>6} {'Score':>6} {'Rank':>4}{RESET}")
        print(f"  {DIM}{'─'*4}  {'─'*34} {'─'*5} {'─'*5} {'─'*6} {'─'*6} {'─'*4}{RESET}")

        for i in range(start, end):
            r = game.level_results[i]
            if r is None:
                continue
            rc = RANK_COLORS.get(r["rank"], "")
            if r["skipped"]:
                print(
                    f"  {DIM}{r['level']:>4}  {r['path']:<34} {'--':>5} {'--':>5} {'--':>6} {'--':>6}    -{RESET}"
                )
            else:
                print(
                    f"  {r['level']:>4}  {r['path']:<34} {r['moves']:>5} {r['pushes']:>5} {fmt_time(r['time']):>6} {r['score']:>6} {rc}{r['rank']:>4}{RESET}"
                )

        print(f"  {DIM}{'─'*4}  {'─'*34} {'─'*5} {'─'*5} {'─'*6} {'─'*6} {'─'*4}{RESET}")

    total_s = game.total_score()
    total_t = game.total_time()

    if solved > 0:
        avg_score = total_s / solved
        if avg_score <= 10:
            overall_rank = "S"
        elif avg_score <= 20:
            overall_rank = "A"
        elif avg_score <= 40:
            overall_rank = "B"
        elif avg_score <= 70:
            overall_rank = "C"
        else:
            overall_rank = "D"
    else:
        overall_rank = "-"

    orc = RANK_COLORS.get(overall_rank, "")
    print(
        f"  {BOLD}{'':>4}  {'TOTAL':<34} {'':>5} {'':>5} {fmt_time(total_t):>6} {total_s:>6} {orc}{overall_rank:>4}{RESET}"
    )
    print()

    # save score
    scores = load_scores()
    entry = {
        "player": player,
        "total_score": total_s,
        "total_time": round(total_t, 1),
        "solved": solved,
        "skipped": skipped,
        "rank": overall_rank,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    if "runs" not in scores:
        scores["runs"] = []
    scores["runs"].append(entry)
    save_scores(scores)

    # leaderboard
    all_runs = scores["runs"]
    ranked = sorted(all_runs, key=lambda x: (-x["solved"], x["total_score"]))

    print(f"  {BOLD}Leaderboard{RESET} {DIM}(top 10){RESET}")
    print(f"  {DIM}{'#':>3}  {'Player':<20} {'Solved':>6} {'Score':>7} {'Time':>7} {'Rank':>4}{RESET}")
    print(f"  {DIM}{'─'*3}  {'─'*20} {'─'*6} {'─'*7} {'─'*7} {'─'*4}{RESET}")

    for idx, run in enumerate(ranked[:10]):
        rc = RANK_COLORS.get(run.get("rank", "-"), "")
        marker = " ◀" if run is entry else ""
        print(
            f"  {idx+1:>3}  {run['player']:<20} {run['solved']:>6} {run['total_score']:>7} {fmt_time(run['total_time']):>7} {rc}{run.get('rank', '-'):>4}{RESET}{YELLOW}{marker}{RESET}"
        )
    print()
    print(f"  {DIM}Scores saved to {SCORE_FILE.name}{RESET}")
    print()


def render_menu():
    os.system("clear" if os.name != "nt" else "cls")
    print(f"{BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}")
    print(f"{BOLD}  dirclean{RESET} {DIM}v2.0.0 — directory cleanup tool{RESET}")
    print(f"{BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}")
    print()

    save = load_game()
    if save:
        lvl = save["current_level"] + 1
        solved = sum(1 for r in save.get("level_results", []) if r and not r.get("skipped"))
        ts = save.get("timestamp", "?")
        print(f"  {DIM}Save data found:{RESET} Level {lvl}, {solved} cleaned")
        print(f"  {DIM}Last played:{RESET} {ts}")
        print()
        print(f"    {CYAN}c{RESET} — Continue from Level {lvl}")
        print(f"    {CYAN}n{RESET} — New game (start from Level 1)")
        print(f"    {CYAN}d{RESET} — Delete save data")
        print(f"    {CYAN}q{RESET} — Quit")
    else:
        print(f"  {DIM}No save data found.{RESET}")
        print()
        print(f"    {CYAN}n{RESET} — New game")
        print(f"    {CYAN}q{RESET} — Quit")

    print()
    return save


# ── Input ──────────────────────────────────────────────────────


def getch():
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == "\x1b":
            ch2 = sys.stdin.read(1)
            ch3 = sys.stdin.read(1)
            return ch + ch2 + ch3
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


# ── Main ───────────────────────────────────────────────────────


def main():
    # Menu
    while True:
        save = render_menu()
        key = getch()

        if key in ("q", "\x03"):
            os.system("clear" if os.name != "nt" else "cls")
            print(f"{DIM}dirclean: session ended.{RESET}")
            return

        elif key == "c" and save:
            game = Sokoban()
            game.restore_from_save(save)
            game.load_level(game.level_num)
            break

        elif key == "n":
            game = Sokoban()
            game.load_level(0)
            break

        elif key == "d" and save:
            clear_save()
            continue

    render(game)

    while True:
        key = getch()

        if key in ("q", "\x03"):
            save_game(game)
            render_scorecard(game)
            break

        elif key in ("h", "\x1b[D"):
            game.move(0, -1)
        elif key in ("l", "\x1b[C"):
            game.move(0, 1)
        elif key in ("k", "\x1b[A"):
            game.move(-1, 0)
        elif key in ("j", "\x1b[B"):
            game.move(1, 0)

        elif key == "u":
            game.undo()

        elif key == "r":
            game.load_level(game.level_num)

        elif key == "n":
            game.record_skip()
            if game.level_num + 1 < game.max_level:
                game.load_level(game.level_num + 1)
                save_game(game)
            else:
                save_game(game)
                render_scorecard(game)
                break

        else:
            continue

        if game.is_complete():
            game.record_level()
            result = game.level_results[game.level_num]
            render_complete(game, result)
            getch()
            if game.level_num + 1 < game.max_level:
                game.load_level(game.level_num + 1)
                save_game(game)
            else:
                save_game(game)
                render_scorecard(game)
                break

        render(game)


if __name__ == "__main__":
    main()
