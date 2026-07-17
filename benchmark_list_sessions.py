import time
import os
from pathlib import Path
import json

def setup_files(num_files):
    os.makedirs('test_sessions', exist_ok=True)
    for i in range(num_files):
        with open(f'test_sessions/session_{i}.jsonl', 'w') as f:
            f.write('{"_type": "metadata", "metadata": {"nickname": "test"}, "key": "test_key", "created_at": "2023-01-01T00:00:00"}\n')

def run_glob_stat(dir_path):
    mtimes = []
    for path in dir_path.glob("*.jsonl"):
        mtimes.append(path.stat().st_mtime)
    return len(mtimes)

def run_scandir(dir_path):
    mtimes = []
    for entry in os.scandir(dir_path):
        if entry.is_file() and entry.name.endswith(".jsonl"):
            mtimes.append(entry.stat().st_mtime)
    return len(mtimes)

if __name__ == "__main__":
    setup_files(10000)
    p = Path('test_sessions')

    t0 = time.time()
    run_glob_stat(p)
    t1 = time.time()
    print(f"glob + stat: {t1 - t0:.4f} seconds")

    t0 = time.time()
    run_scandir(p)
    t1 = time.time()
    print(f"scandir: {t1 - t0:.4f} seconds")
