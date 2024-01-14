from pathlib import Path
import sys

DIFF_LIMIT = 512
FUNC_ALIGNMENT = 16 # on windows functions are aligned to 16 bytes

HELP_MESSAGE = "after running version tracking, there's a percentage of functions that may be lost. this script aims to find such functions and has a fairly high success rate in that. \
\n\n\
before running, you need to dump the known functions in the old and new binaries into text files, and then run this script against the two files. \
it will then try to find every missing function, and tell you the guessed offset and the confidence of the algorithm in that offset. \
\n\n\
note: this is nothing more than simple math so any output offset may not precisely match the target function. it may be a few instructions in, or it may be in a previous function in the binary, though 100% confidence usually indicates an exact match. \
it is on *you* to check every match and adjust properly. even with 100% confidence, the guesses can be wrong (albeit not commonly), so if it looks off, double check. \
\n\n\
the script is also *not* expected to work across different platforms in any capacity, and issues may also arise when trying very distant versions on the same platform. your experience may vary."

col = lambda num: f"\u001b[38;5;{num}m"
COLOR_RED = col(196)
COLOR_RESET = col(0)
COLOR_WHITE = col(15)
COLOR_GRAY = col(248)
COLOR_LIME = col(46)
COLOR_LIGHT_GREEN = col(83)
COLOR_GREEN_YELLOW = col(154)
COLOR_YELLOW = col(220)
COLOR_ORANGE = col(202)
STYLE_BOLD = "\033[1m" # col(230)
STYLE_RESET = "\033[0m"

def find_idx(funclist: list, query: str) -> int:
    for (n, (funcname, _)) in enumerate(funclist):
        if funcname == query: return n

    return -1

def print_with(msg: str, style: str):
    print(f"{style}{msg}{COLOR_RESET}")

if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == '--help':
        print(f"usage: {sys.executable} {sys.argv[0]} <older_path> <newer_path>\n")
        print(HELP_MESSAGE)
        exit(0)

    if len(sys.argv) < 3:
        print(f"usage: {sys.executable} {sys.argv[0]} <older_path> <newer_path>")
        print("or use --help to get a brief description of what this script does")
        exit(1)

    older_path = Path(sys.argv[1])
    newer_path = Path(sys.argv[2])

    older_funcs = list(f.split(' - ') for f in older_path.read_text().splitlines() if f)
    newer_funcs = list(f.split(' - ') for f in newer_path.read_text().splitlines() if f)

    for older_idx, (function, function_offset) in enumerate(older_funcs):
        # if the function already exists in the new file, skip it
        if find_idx(newer_funcs, function) != -1:
            continue

        # the first and last functions are always going to have only 1 neighbor, so skip them
        if older_idx == 0 or older_idx == len(older_funcs) - 1:
            print_with(f"skipping {function}, impossible to find two neighboring functions for it", COLOR_GRAY)
            continue

        # find neighboring functions

        idx_before = older_idx
        newer_idx_before = -1
        while idx_before > 0 and newer_idx_before == -1:
            idx_before -= 1
            newer_idx_before = find_idx(newer_funcs, older_funcs[idx_before][0])

        idx_after = older_idx
        newer_idx_after = -1
        while idx_after < len(older_funcs) - 2 and newer_idx_after == -1:
            idx_after += 1
            newer_idx_after = find_idx(newer_funcs, older_funcs[idx_after][0])

        if newer_idx_before == -1 or newer_idx_after == -1:
            print_with(f"Failed to find neighboring functions for {function}, skipping", COLOR_GRAY)
            continue

        # parse the hex offsets
        newer_func_before = int(newer_funcs[newer_idx_before][1], 16)
        newer_func_after = int(newer_funcs[newer_idx_after][1], 16)
        older_func_before = int(older_funcs[idx_before][1], 16)
        older_func_after = int(older_funcs[idx_after][1], 16)

        # find and compare the difference between 2 neighbors in both files
        newer_whole_diff = newer_func_after - newer_func_before
        older_whole_diff = older_func_after - older_func_before

        diff_diff = abs(newer_whole_diff - older_whole_diff)
        if diff_diff > DIFF_LIMIT:
            print_with(f"skipping {function}, hard to estimate the correct location ({diff_diff}b distance difference)", COLOR_GRAY)
            continue

        # approximate where the function can be: (newfunc3 - newfunc1) * (oldfunc2 - oldfunc1) / (oldfunc3 - oldfunc1)
        older_target_diff = int(function_offset, 16) - older_func_before
        mult = older_target_diff / older_whole_diff
        newer_target_diff = newer_whole_diff * mult
        guess = int(newer_func_before + newer_target_diff)

        # align the function
        guess = (guess + (FUNC_ALIGNMENT - 1)) & ~(FUNC_ALIGNMENT - 1)

        # confidence depends solely on the distance between two neighboring functions
        # if the distance is the same in both files, confidence is 100%, otherwise it will be lower.
        # this is also not perfect, because if functions get modified but stay the same size (or get reordered), then you may get a wrong guess with 100% confidence.
        # but that doesn't happen often so it is not a big deal, as long as you review every match manually.
        confidence = ((DIFF_LIMIT - diff_diff) / DIFF_LIMIT)

        if confidence >= 0.9:
            color = COLOR_LIME
        elif confidence >= 0.7:
            color = COLOR_GREEN_YELLOW
        elif confidence >= 0.5:
            color = COLOR_YELLOW
        else:
            color = COLOR_ORANGE

        print_with(f"{function} - {COLOR_WHITE}{STYLE_BOLD}{hex(guess)}{STYLE_RESET} (confidence {color}{(confidence * 100):.1f}%{COLOR_WHITE})", color)
