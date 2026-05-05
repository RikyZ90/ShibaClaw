import time

with open("shibaclaw/agent/memory.py", "r", encoding="utf-8") as f:
    content = f.read()
    
# Replace read_user_profile
old_user = """    def read_user_profile(self) -> str:
        if self.user_file.exists():
            return self.user_file.read_text(encoding="utf-8")
        return \"\""""

new_user = """    def read_user_profile(self) -> str:
        if not self.user_file.exists():
            return ""
        try:
            mtime = self.user_file.stat().st_mtime_ns
        except FileNotFoundError:
            return ""
        if getattr(self, "_user_mtime", 0) == mtime:
            return self._user_cache
        content = self.user_file.read_text(encoding="utf-8")
        self._user_mtime = mtime
        self._user_cache = content
        return content"""

# Replace read_long_term
old_lt = """    def read_long_term(self) -> str:
        if self.memory_file.exists():
            return self.memory_file.read_text(encoding="utf-8")
        return \"\""""

new_lt = """    def read_long_term(self) -> str:
        if not self.memory_file.exists():
            return ""
        try:
            mtime = self.memory_file.stat().st_mtime_ns
        except FileNotFoundError:
            return ""
        if getattr(self, "_mem_mtime", 0) == mtime:
            return self._mem_cache
        content = self.memory_file.read_text(encoding="utf-8")
        self._mem_mtime = mtime
        self._mem_cache = content
        return content"""

if old_user in content:
    content = content.replace(old_user, new_user)
    print("Replaced read_user_profile")
if old_lt in content:
    content = content.replace(old_lt, new_lt)
    print("Replaced read_long_term")

with open("shibaclaw/agent/memory.py", "w", encoding="utf-8") as f:
    f.write(content)
