
path = r'c:\Users\Rikyz\.gemini\antigravity\scratch\shibaclaw_next\shibaclaw\cli\gateway.py'
utils_path = r'c:\Users\Rikyz\.gemini\antigravity\scratch\shibaclaw_next\shibaclaw\cli\gateway_utils.py'

with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

start_idx = 0
for i, line in enumerate(lines):
    if line.startswith("@dataclass(frozen=True)"):
        start_idx = i
        break

end_idx = 0
for i in range(start_idx, len(lines)):
    if lines[i].startswith("async def _cancel_all_tasks_gracefully():") or lines[i].startswith("async def _cancel_all_tasks_gracefully() -> None:"):
        end_idx = i
        break

if start_idx > 0 and end_idx > 0:
    extracted_lines = lines[start_idx:end_idx]
    
    with open(utils_path, 'w', encoding='utf-8') as f:
        f.write('"""Utility functions for the gateway service."""\n\n')
        f.write('from __future__ import annotations\n\n')
        f.write('import os\n')
        f.write('from dataclasses import dataclass\n')
        f.write('from typing import Any, Awaitable, Callable\n\n')
        f.write('from loguru import logger\n\n')
        f.writelines(extracted_lines)
    
    new_lines = lines[:start_idx]
    new_lines.append('from .gateway_utils import (\n')
    new_lines.append('    HeartbeatTarget,\n')
    new_lines.append('    resolve_webui_session_key,\n')
    new_lines.append('    resolve_automation_target,\n')
    new_lines.append('    deliver_scheduled_job_result,\n')
    new_lines.append('    select_heartbeat_target,\n')
    new_lines.append('    resolve_heartbeat_targets,\n')
    new_lines.append('    notify_webui_session,\n')
    new_lines.append(')\n\n')
    new_lines.extend(lines[end_idx:])
    
    with open(path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    print(f"Extracted {len(extracted_lines)} lines to gateway_utils.py")
else:
    print(f"Failed to find indices. Start: {start_idx}, End: {end_idx}")
