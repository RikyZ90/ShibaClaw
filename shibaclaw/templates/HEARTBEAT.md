# Heartbeat Tasks

This file is checked by your shibaclaw heartbeat service.
Configure **interval**, **model**, **profile** and **output channel** from the WebUI Settings → Heartbeat tab.

If this file has no tasks (only headers and comments), the agent will skip the heartbeat.

### Optional: YAML frontmatter overrides

You can add a YAML frontmatter block at the top of this file to override specific settings locally (takes priority over the WebUI):

```yaml
---
session_key: heartbeat:default
profile_id: builder
targets:
  webui: recent
  telegram: "12345"
---
```

Supported override fields: `session_key`, `profile_id`, `targets`.
`enabled` and `interval_min` stay in the global settings only.

## Active Tasks

<!-- Add your periodic tasks below this line -->


## Completed

<!-- Move completed tasks here or delete them -->

