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
it is on *you* to check every match and adjust properly. even with 100% confidence, the guesses can be wrong (albeit very rarely), so if it looks off, double check. \
\n\n\
the script is also *not* expected to work between platforms in any capacity, and issues may also arise when trying very distant versions on the same platform. your experience may vary."

def find_idx(funclist: list, query: str) -> int:
    for (n, (funcname, _)) in enumerate(funclist):
        if funcname == query: return n

    return -1

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
        if find_idx(newer_funcs, function) != -1:
            continue

        if older_idx == 0 or older_idx == len(older_funcs) - 1:
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
            print("Failed to find neighboring functions for", function)
            continue

        newer_func_before = int(newer_funcs[newer_idx_before][1], 16)
        newer_func_after = int(newer_funcs[newer_idx_after][1], 16)

        before_neighbor = older_funcs[idx_before][0]
        after_neighbor = older_funcs[idx_after][0]

        older_func_before = int(older_funcs[idx_before][1], 16)
        older_func_after = int(older_funcs[idx_after][1], 16)

        newer_whole_diff = newer_func_after - newer_func_before
        older_whole_diff = older_func_after - older_func_before

        diff_diff = abs(newer_whole_diff - older_whole_diff)
        if diff_diff > DIFF_LIMIT:
            print(f"skipping {function}, hard to estimate the correct location ({diff_diff}B distance difference)")
            continue

        older_target_diff = int(function_offset, 16) - older_func_before
        mult = older_target_diff / older_whole_diff
        newer_target_diff = newer_whole_diff * mult

        guess = int(newer_func_before + newer_target_diff)
        # align the function
        guess = (guess + (FUNC_ALIGNMENT - 1)) & ~(FUNC_ALIGNMENT - 1)

        #print(f"{function} (used {before_neighbor} and {after_neighbor}):", hex(guess))
        confidence = ((DIFF_LIMIT - diff_diff) / DIFF_LIMIT) * 100
        print(f"{function} - {hex(guess)} (confidence {confidence:.1f}%)")
