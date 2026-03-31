#!/usr/bin/env python3
"""Write all redesigned files to the correct paths."""
import os
import subprocess

def resolve_path(unix_path):
    """Convert unix /tmp path to proper Windows path."""
    r = subprocess.run(['cygpath', '-w', unix_path], capture_output=True, text=True)
    return r.stdout.strip()

def write_file(unix_path, content):
    win_path = resolve_path(unix_path)
    os.makedirs(os.path.dirname(win_path), exist_ok=True)
    with open(win_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Written: {unix_path} ({len(content)} chars)")

print("Writer ready")
