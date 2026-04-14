---
enabled: true
interval_s: 1800
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
- enabled: turn heartbeat execution on or off for this file
- interval_s: seconds between heartbeat checks
- session_key: stable session used across beats
- profile_id: existing profile to use (default, builder, planner, reviewer, hacker, ...)
- targets: explicit output channels; use recent/latest/auto to reuse the most recent session for that channel

If this file has no tasks (only headers and comments), the agent will skip the heartbeat.

## Active Tasks

<!-- Add your periodic tasks below this line -->


## Completed

<!-- Move completed tasks here or delete them -->

