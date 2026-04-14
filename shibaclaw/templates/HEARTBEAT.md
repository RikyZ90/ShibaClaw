---
session_key: heartbeat:default
profile_id: default
targets:
  webui: recent
  # telegram: "12345"
---

# Heartbeat Tasks

This file is checked by your shibaclaw heartbeat service.
Edit the YAML block above to control this heartbeat directly.

Supported fields in the YAML block:
- session_key: stable session used across beats
- profile_id: existing profile to use (default, builder, planner, reviewer, hacker, ...)
- targets: explicit output channels; use recent/latest/auto to reuse the most recent session for that channel

`enabled` and `interval_s` stay in the global settings, not in this file.

If this file has no tasks (only headers and comments), the agent will skip the heartbeat.

## Active Tasks

<!-- Add your periodic tasks below this line -->


## Completed

<!-- Move completed tasks here or delete them -->

