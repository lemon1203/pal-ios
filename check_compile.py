"""本地编译闸门：对比「打补丁前 / 打补丁后」的错误集合，只判断新增错误。

用法：python check_compile.py <打完补丁的源码目录> <原始源码目录>
"""
import re
import subprocess
import sys
import tempfile
import shutil
import os

SDL_INC = r"C:\Users\Administrator\Desktop\test\_sdl3_headers\include"
CLANG = r"C:\msys64\ucrt64\bin\clang.exe"
FILES = ["video.c", "input.c", "main.c", "uigame.c", "map.c", "battle.c"]

ERR_RE = re.compile(r"^([^:]+):(\d+):\d+:\s+(fatal error|error):\s+(.*)$")


def scan(root):
    errors = set()
    for f in FILES:
        path = os.path.join(root, f)
        if not os.path.isfile(path):
            continue
        proc = subprocess.run(
            [CLANG, "-fsyntax-only", "-I.", "-I./sdl_compat", "-I./ios",
             "-I" + SDL_INC, "-I" + os.path.join(SDL_INC, "SDL3"), f],
            cwd=root, capture_output=True, text=True, errors="replace")
        for line in (proc.stdout + proc.stderr).splitlines():
            m = ERR_RE.match(line.strip())
            if m:
                errors.add((m.group(1), m.group(4)))
    return errors


def main():
    patched = sys.argv[1]
    original = sys.argv[2]

    base = scan(original)
    cur = scan(patched)

    new = cur - base
    if new:
        print("新增错误 %d 条：" % len(new))
        for f, msg in sorted(new)[:20]:
            print("   %-12s %s" % (os.path.basename(f), msg))
        sys.exit(1)

    print("✔ 没有新增编译错误（基线已有 %d 条 SDL3 差异告警）" % len(base))


if __name__ == "__main__":
    main()
