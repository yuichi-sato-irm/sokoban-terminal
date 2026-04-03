#!/usr/bin/env python3
"""
dirclean v1.3.2 — Directory Cleanup Tool
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

# ── Level data ─────────────────────────────────────────────────
# # = wall, @ = player, $ = box, . = target
# + = player on target, * = box on target

LEVELS = [
    # ── Easy (1-5) ──
    {
        "path": "~/projects/api/src",
        "map": [
            "#####",
            "#   #",
            "#@$.#",
            "#   #",
            "#####",
        ],
    },
    {
        "path": "~/projects/api/config",
        "map": [
            "######",
            "#    #",
            "# @$.#",
            "#  $.#",
            "#    #",
            "######",
        ],
    },
    {
        "path": "~/services/auth/lib",
        "map": [
            "#####",
            "#  .#",
            "#   #",
            "# $ #",
            "# @ #",
            "#####",
        ],
    },
    {
        "path": "~/services/auth/test",
        "map": [
            "######",
            "#  . #",
            "# $  #",
            "# .$ #",
            "#  @ #",
            "######",
        ],
    },
    {
        "path": "~/services/auth/migrations",
        "map": [
            "######",
            "# .  #",
            "#  $ #",
            "#  $ #",
            "#  . #",
            "#  @ #",
            "######",
        ],
    },
    # ── Medium (6-10) ──
    {
        "path": "~/data/pipeline/jobs",
        "map": [
            "######",
            "#.   #",
            "#  $ #",
            "#  $ #",
            "#   .#",
            "#  @ #",
            "######",
        ],
    },
    {
        "path": "~/data/pipeline/output",
        "map": [
            "######",
            "#   .#",
            "# $  #",
            "##$  #",
            " #. @#",
            " #####",
        ],
    },
    {
        "path": "~/data/pipeline/staging",
        "map": [
            " ####",
            " #  #",
            "## .#",
            "# $ #",
            "# $ #",
            "# .@#",
            "#####",
        ],
    },
    {
        "path": "~/data/etl/scripts",
        "map": [
            "#####",
            "#.  ##",
            "# $  #",
            "## $ #",
            " #.@ #",
            " #####",
        ],
    },
    {
        "path": "~/data/etl/logs",
        "map": [
            "  ####",
            "###  #",
            "#. $ #",
            "# .$ #",
            "#  @ #",
            "######",
        ],
    },
    # ── Hard (11-15) ──
    {
        "path": "~/infra/terraform/modules",
        "map": [
            " #####",
            " # . #",
            "## $ #",
            "#  $ #",
            "# .# #",
            "#  @ #",
            "######",
        ],
    },
    {
        "path": "~/infra/terraform/envs",
        "map": [
            "#######",
            "#  .  #",
            "# $#$ #",
            "#  .  #",
            "#  @  #",
            "#######",
        ],
    },
    {
        "path": "~/infra/deploy/staging",
        "map": [
            "  #####",
            "###   #",
            "# . # #",
            "# $$  #",
            "##.  ##",
            " #   #",
            " # @ #",
            " #####",
        ],
    },
    {
        "path": "~/infra/deploy/production",
        "map": [
            "######",
            "#    #",
            "# .$.#",
            "# $  #",
            "# $. #",
            "#  @ #",
            "######",
        ],
    },
    {
        "path": "~/infra/k8s/manifests",
        "map": [
            "######",
            "#  . #",
            "# $$ #",
            "#  . #",
            "# @  #",
            "######",
        ],
    },
    # ── Expert (16-20) ──
    {
        "path": "~/frontend/app/components",
        "map": [
            " ######",
            "##    #",
            "#  $# #",
            "# .$.@#",
            "# $ # #",
            "# .   #",
            "#######",
        ],
    },
    {
        "path": "~/frontend/app/hooks",
        "map": [
            "#######",
            "#     #",
            "# .$. #",
            "# $.$ #",
            "# .$  #",
            "#  @  #",
            "#######",
        ],
    },
    {
        "path": "~/frontend/app/store",
        "map": [
            "#####",
            "# . #",
            "# $ ##",
            "# .$ #",
            "## $ #",
            " # . #",
            " # @ #",
            " #####",
        ],
    },
    {
        "path": "~/frontend/app/utils",
        "map": [
            "  #####",
            "### . #",
            "# $ $ #",
            "# . . #",
            "# $ ###",
            "# @  #",
            "######",
        ],
    },
    {
        "path": "~/frontend/app/dist",
        "map": [
            "########",
            "#      #",
            "# .$.$ #",
            "# .$ ##",
            "# .$ #",
            "#  @ #",
            "######",
        ],
    },
]

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

SCORE_FILE = Path(__file__).parent / ".dirclean_scores.json"


def calc_score(moves, pushes, elapsed, num_targets):
    """Lower is better. Base = moves + pushes*2, time penalty after 60s per target."""
    base = moves + pushes * 2
    time_limit = num_targets * 60
    time_penalty = max(0, int((elapsed - time_limit) / 10))
    return base + time_penalty


def calc_rank(score, num_targets):
    """Return letter rank based on score relative to target count."""
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
    """Get player name from git config or environment."""
    try:
        import subprocess

        result = subprocess.run(
            ["git", "config", "user.name"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    return os.environ.get("USER", "anonymous")


# ── Game logic ─────────────────────────────────────────────────


class Sokoban:
    def __init__(self):
        self.level_num = 0
        self.grid = []
        self.moves = 0
        self.pushes = 0
        self.history = []
        self.max_level = len(LEVELS)
        # scoring
        self.level_start_time = 0.0
        self.level_results = []  # list of dicts per level
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
                if ch == ".":
                    return False
                if ch == "+":
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
        result = {
            "level": self.level_num + 1,
            "path": LEVELS[self.level_num]["path"],
            "moves": self.moves,
            "pushes": self.pushes,
            "time": round(elapsed, 1),
            "score": score,
            "rank": rank,
            "skipped": False,
        }
        # Replace or append
        while len(self.level_results) <= self.level_num:
            self.level_results.append(None)
        self.level_results[self.level_num] = result

    def record_skip(self):
        while len(self.level_results) <= self.level_num:
            self.level_results.append(None)
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

    def total_score(self):
        return sum(
            r["score"] for r in self.level_results if r and not r["skipped"]
        )

    def total_time(self):
        return sum(
            r["time"] for r in self.level_results if r and not r["skipped"]
        )


# ── Display ────────────────────────────────────────────────────


def fmt_time(seconds):
    m, s = divmod(int(seconds), 60)
    return f"{m}:{s:02d}"


def render(game):
    os.system("clear" if os.name != "nt" else "cls")
    lv = LEVELS[game.level_num]
    done, total = game.count_targets()
    elapsed = time.time() - game.level_start_time

    diff_label = ""
    if game.level_num < 5:
        diff_label = f"{GREEN}EASY{RESET}"
    elif game.level_num < 10:
        diff_label = f"{YELLOW}MEDIUM{RESET}"
    elif game.level_num < 15:
        diff_label = f"{RED}HARD{RESET}"
    else:
        diff_label = f"{RED}{BOLD}EXPERT{RESET}"

    print(f"{BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}")
    print(f"{BOLD}  dirclean{RESET} {DIM}v1.3.2 — directory cleanup tool{RESET}")
    print(f"{BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}")
    print()
    print(
        f"  {DIM}Scanning:{RESET} {CYAN}{lv['path']}{RESET}"
        f"   {DIM}[{game.level_num + 1}/{game.max_level}]{RESET}"
        f"  {diff_label}"
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
    print(f"  {DIM}← ↑ ↓ → move   u undo   r reset   n skip   q quit{RESET}")
    print()


def render_complete(game, result):
    render(game)
    rank = result["rank"]
    rank_colors = {"S": f"{YELLOW}{BOLD}", "A": f"{GREEN}{BOLD}", "B": f"{CYAN}", "C": f"{WHITE}", "D": f"{DIM}"}
    rc = rank_colors.get(rank, "")
    print(f"  {GREEN}{BOLD}✓ Directory cleaned!{RESET}")
    print(
        f"  {DIM}Score:{RESET} {BOLD}{result['score']}{RESET}"
        f"  {DIM}Rank:{RESET} {rc}{rank}{RESET}"
        f"  {DIM}Time:{RESET} {fmt_time(result['time'])}"
    )
    print(f"  {DIM}Press any key to continue...{RESET}")
    print()


def render_scorecard(game):
    os.system("clear" if os.name != "nt" else "cls")
    player = get_player_name()
    solved = sum(1 for r in game.level_results if r and not r["skipped"])
    skipped = sum(1 for r in game.level_results if r and r["skipped"])

    print(f"{BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}")
    print(f"{BOLD}  dirclean{RESET} {DIM}— session report{RESET}")
    print(f"{BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}")
    print()
    print(f"  {DIM}User:{RESET} {CYAN}{player}{RESET}   {DIM}Cleaned:{RESET} {solved}/{game.max_level}   {DIM}Skipped:{RESET} {skipped}")
    print()

    rank_colors = {"S": f"{YELLOW}{BOLD}", "A": f"{GREEN}{BOLD}", "B": f"{CYAN}", "C": f"{WHITE}", "D": f"{DIM}", "-": f"{DIM}"}

    print(f"  {DIM}{'#':>3}  {'Directory':<32} {'Moves':>5} {'Push':>5} {'Time':>6} {'Score':>6} {'Rank':>4}{RESET}")
    print(f"  {DIM}{'─'*3}  {'─'*32} {'─'*5} {'─'*5} {'─'*6} {'─'*6} {'─'*4}{RESET}")

    for i in range(game.max_level):
        if i < len(game.level_results) and game.level_results[i]:
            r = game.level_results[i]
            rc = rank_colors.get(r["rank"], "")
            if r["skipped"]:
                print(
                    f"  {DIM}{r['level']:>3}  {r['path']:<32} {'--':>5} {'--':>5} {'--':>6} {'--':>6}    -{RESET}"
                )
            else:
                print(
                    f"  {r['level']:>3}  {r['path']:<32} {r['moves']:>5} {r['pushes']:>5} {fmt_time(r['time']):>6} {r['score']:>6} {rc}{r['rank']:>4}{RESET}"
                )
        else:
            lv = LEVELS[i]
            print(f"  {DIM}{i+1:>3}  {lv['path']:<32}{'--':>5} {'--':>5} {'--':>6} {'--':>6}    -{RESET}")

    print(f"  {DIM}{'─'*3}  {'─'*32} {'─'*5} {'─'*5} {'─'*6} {'─'*6} {'─'*4}{RESET}")

    total_s = game.total_score()
    total_t = game.total_time()

    # overall rank
    if solved == 0:
        overall_rank = "-"
    else:
        avg = total_s / solved
        avg_targets = sum(
            LEVELS[i]["map"].__str__().count(".") + LEVELS[i]["map"].__str__().count("+")
            for i in range(game.max_level)
        ) / game.max_level
        if avg <= 5 * max(avg_targets, 1) and solved == game.max_level:
            overall_rank = "S"
        elif avg <= 10 * max(avg_targets, 1):
            overall_rank = "A"
        elif avg <= 20 * max(avg_targets, 1):
            overall_rank = "B"
        elif avg <= 35 * max(avg_targets, 1):
            overall_rank = "C"
        else:
            overall_rank = "D"

    orc = rank_colors.get(overall_rank, "")
    print(
        f"  {BOLD}{'':>3}  {'TOTAL':<32} {'':>5} {'':>5} {fmt_time(total_t):>6} {total_s:>6} {orc}{overall_rank:>4}{RESET}"
    )
    print()

    # save
    scores = load_scores()
    entry = {
        "player": player,
        "total_score": total_s,
        "total_time": round(total_t, 1),
        "solved": solved,
        "skipped": skipped,
        "rank": overall_rank,
        "levels": [r for r in game.level_results if r],
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    if "runs" not in scores:
        scores["runs"] = []
    scores["runs"].append(entry)
    save_scores(scores)

    # leaderboard
    all_runs = scores["runs"]
    # sort by: solved desc, then total_score asc
    ranked = sorted(all_runs, key=lambda x: (-x["solved"], x["total_score"]))

    print(f"  {BOLD}Leaderboard{RESET} {DIM}(top 10){RESET}")
    print(f"  {DIM}{'#':>3}  {'Player':<20} {'Solved':>6} {'Score':>7} {'Time':>7} {'Rank':>4}{RESET}")
    print(f"  {DIM}{'─'*3}  {'─'*20} {'─'*6} {'─'*7} {'─'*7} {'─'*4}{RESET}")

    for idx, run in enumerate(ranked[:10]):
        rc = rank_colors.get(run.get("rank", "-"), "")
        marker = " ◀" if run is entry else ""
        print(
            f"  {idx+1:>3}  {run['player']:<20} {run['solved']:>6} {run['total_score']:>7} {fmt_time(run['total_time']):>7} {rc}{run.get('rank', '-'):>4}{RESET}{YELLOW}{marker}{RESET}"
        )
    print()
    print(f"  {DIM}Scores saved to {SCORE_FILE.name}{RESET}")
    print()


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
    game = Sokoban()
    game.load_level(0)
    render(game)

    while True:
        key = getch()

        if key in ("q", "\x03"):  # q or Ctrl+C
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
            else:
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
            else:
                render_scorecard(game)
                break

        render(game)


if __name__ == "__main__":
    main()
