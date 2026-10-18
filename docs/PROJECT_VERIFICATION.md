# Project verification

`spawn` and `spawn_mea` can run configured project checks after delegated work finishes. Execution, the MEA agent's audit verdict, and executable verification are separate outcomes. A worker saying “PASSED” does not pass a check.

## Configure a project

Add `tools.verification` to your ShibaClaw `config.json` (normally `~/.shibaclaw/config.json`), preserving the existing settings:

```json
{
  "tools": {
    "verification": {
      "projects": {
        "my-app": {
          "path": "projects/my-app",
          "checks": [
            {
              "name": "Unit tests",
              "command": "python -m pytest tests/ -q",
              "timeout": 120
            },
            {
              "name": "Lint",
              "command": "python -m ruff check .",
              "timeout": 60
            }
          ]
        }
      }
    }
  }
}
```

Paths are relative to the ShibaClaw workspace, or absolute paths when the session permits them. The directory must already exist. Workspace restrictions also apply to resolved symlinks. The worker's relative file operations, terminal commands, and configured checks use the selected project directory. No branch or worktree is created.

Commands come from the operator's configuration. The model selects a registered project name, not arbitrary verification commands. Configure up to ten checks per project; each has a timeout from 1 to 600 seconds (default 120). Commands use the exec tool's argument parsing without a shell: put pipelines, redirects, or multi-command workflows into a script and configure a command such as `python scripts/verify.py`. Install the required test/build tools in the runtime environment first.

Reload the configuration through the existing settings flow or restart the gateway after editing the file directly. Existing configurations remain valid and do not run additional commands.

## Select verification for a delegation

Configured project names appear in the `verification_project` parameter of both delegation tools. For example:

```json
{
  "task": "Fix the parser regression and update the relevant tests",
  "label": "Parser fix",
  "verification_project": "my-app"
}
```

Omitting `verification_project` leaves verification **not configured** for that task, including research tasks. This first version verifies selected delegations; it does not automatically validate every ordinary chat response or command executed directly by the main agent.

## Evidence and outcomes

Chat cards display execution and verification separately. Expand the task details for the project directory, configured commands, per-check status, process exit code, duration, and output. MEA's text verdict is labelled **Agent audit**.

Verification is **passed** only when every configured check ran successfully and returned exit code zero. Nonzero exit codes fail verification even if stdout or the auditor says `PASSED`. Guard rejection, missing executables, permission restrictions, timeouts, cancellation, and interrupted runs cannot pass. All checks run sequentially unless the task is stopped or interrupted; successful checks remain visible when a later check fails.

The task's lifecycle `status` remains separate from `verification.status`: a `succeeded` execution can have `failed` verification. Consumers must inspect `verification.status` before treating configured checks as passed. A passed check proves its configured condition; it does not guarantee that the entire implementation is correct.

Checks inherit the task's exec capability and session permission mode, use the existing command/install guards, and participate in the turn journal. `/stop` cancels running verification; `/stop idle` finishes the active command and prevents subsequent checks. The worker's overall timeout also covers verification. A restart marks unfinished work and pending checks incomplete, without automatically replaying commands.

Evidence is stored with the bounded task history and restored after reconnecting or switching sessions. Private task evidence stays in memory. Output is bounded to a head/tail excerpt of approximately 6,000 characters per check, with truncation indicated. Avoid putting credentials in command arguments or check output.
