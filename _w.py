import os, subprocess

def resolve_path(p):
    r = subprocess.run(["cygpath", "-w", p], capture_output=True, text=True)
    return r.stdout.strip()

def wf(p, c):
    wp = resolve_path(p)
    os.makedirs(os.path.dirname(wp), exist_ok=True)
    with open(wp, "w", encoding="utf-8") as f:
        f.write(c)
    print(f"Written: {p} ({len(c)} chars)")

import sys, base64
data = base64.b64decode(sys.stdin.read()).decode("utf-8")
target = sys.argv[1]
wf(target, data)
