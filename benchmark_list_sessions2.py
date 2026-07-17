import time
import os
from pathlib import Path
import json

def setup_files(num_files):
    os.makedirs('test_sessions', exist_ok=True)
    for i in range(num_files):
        with open(f'test_sessions/session_{i}.jsonl', 'w') as f:
            f.write('{"_type": "metadata", "metadata": {"nickname": "test"}, "key": "test_key", "created_at": "2023-01-01T00:00:00"}\n')

class TestManager:
    def __init__(self, dir_path):
        self.sessions_dir = Path(dir_path)
        self._list_sessions_cache = {}

    def list_sessions_old(self):
        sessions = []
        new_cache = {}
        for path in self.sessions_dir.glob("*.jsonl"):
            try:
                path_str = str(path)
                mtime = path.stat().st_mtime

                cached_data = self._list_sessions_cache.get(path_str)
                if cached_data and cached_data[0] == mtime:
                    sessions.append(cached_data[1])
                    new_cache[path_str] = cached_data
                    continue

                updated_at = "1234" # datetime.fromtimestamp(mtime).isoformat()
                with open(path, encoding="utf-8") as f:
                    first_line = f.readline().strip()
                    if first_line:
                        data = json.loads(first_line)
                        if data.get("_type") == "metadata":
                            meta = data.get("metadata", {})
                            key = data.get("key") or path.stem.replace("_", ":", 1)
                            session_meta = {
                                "key": key,
                                "nickname": meta.get("nickname"),
                                "profile_id": meta.get("profile_id", "default"),
                                "created_at": data.get("created_at"),
                                "updated_at": updated_at,
                                "path": path_str,
                            }
                            sessions.append(session_meta)
                            new_cache[path_str] = (mtime, session_meta)
            except Exception:
                continue

        self._list_sessions_cache = new_cache
        return sessions

    def list_sessions_new(self):
        sessions = []
        new_cache = {}
        for entry in os.scandir(self.sessions_dir):
            if not entry.is_file() or not entry.name.endswith(".jsonl"):
                continue
            try:
                path_str = entry.path
                mtime = entry.stat().st_mtime

                cached_data = self._list_sessions_cache.get(path_str)
                if cached_data and cached_data[0] == mtime:
                    sessions.append(cached_data[1])
                    new_cache[path_str] = cached_data
                    continue

                updated_at = "1234" # datetime.fromtimestamp(mtime).isoformat()
                with open(entry.path, encoding="utf-8") as f:
                    first_line = f.readline().strip()
                    if first_line:
                        data = json.loads(first_line)
                        if data.get("_type") == "metadata":
                            meta = data.get("metadata", {})
                            key = data.get("key") or entry.name[:-6].replace("_", ":", 1) # .stem
                            session_meta = {
                                "key": key,
                                "nickname": meta.get("nickname"),
                                "profile_id": meta.get("profile_id", "default"),
                                "created_at": data.get("created_at"),
                                "updated_at": updated_at,
                                "path": path_str,
                            }
                            sessions.append(session_meta)
                            new_cache[path_str] = (mtime, session_meta)
            except Exception:
                continue

        self._list_sessions_cache = new_cache
        return sessions

if __name__ == "__main__":
    setup_files(10000)

    mgr_old = TestManager('test_sessions')

    t0 = time.time()
    mgr_old.list_sessions_old()
    t1 = time.time()
    print(f"old (cold): {t1 - t0:.4f} seconds")

    t0 = time.time()
    mgr_old.list_sessions_old()
    t1 = time.time()
    print(f"old (hot): {t1 - t0:.4f} seconds")

    mgr_new = TestManager('test_sessions')

    t0 = time.time()
    mgr_new.list_sessions_new()
    t1 = time.time()
    print(f"new (cold): {t1 - t0:.4f} seconds")

    t0 = time.time()
    mgr_new.list_sessions_new()
    t1 = time.time()
    print(f"new (hot): {t1 - t0:.4f} seconds")
