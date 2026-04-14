# Heartbeat Tasks

This file is checked every 30 minutes by your shibaclaw agent.
Add tasks below that you want the agent to work on periodically.

If this file has no tasks (only headers and comments), the agent will skip the heartbeat.

<!--
Heartbeat settings are configured in config.yaml under gateway.heartbeat:

  gateway:
    heartbeat:
      enabled: true
      interval_s: 1800           # Check every 30 minutes
      session_key: "heartbeat:default"  # Stable session (all beats share the same conversation)
      profile_id: "builder"      # Use an existing profile (e.g. builder, hacker, planner)
      targets:                   # Explicit output channels (omit for auto-detection)
        telegram: "12345"        # channel: chat_id
        webui: "recent"          # deliver to WebUI too
-->

## Active Tasks

<!-- Add your periodic tasks below this line -->


## Completed

<!-- Move completed tasks here or delete them -->

