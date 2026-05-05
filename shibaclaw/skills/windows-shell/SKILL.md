---
name: windows-shell
description: Manage long-running background jobs and interactive workflows on Windows using PowerShell Jobs (Start-Job, Receive-Job) — the Windows equivalent of tmux sessions.
metadata: {"shibaclaw":{"emoji":"🪟","os":["windows"]}}
---

# Windows Shell Skill

Use PowerShell Jobs when you need to run tasks in the background, keep processes alive across multiple steps, or run several commands in parallel on Windows.  
This skill is the Windows counterpart of the `tmux` skill (available on Linux/macOS).

---

## Quick-start: start a background job

```powershell
# Start a background job and keep a reference
$job = Start-Job -Name "myTask" -ScriptBlock {
    # Replace with the real command
    python -u my_script.py
}
Write-Host "Job started: $($job.Id) ($($job.Name))"
```

---

## Check job status

```powershell
# List all jobs
Get-Job

# Check a specific job
Get-Job -Name "myTask" | Select-Object Id, Name, State, HasMoreData
```

States: `Running`, `Completed`, `Failed`, `Stopped`.

---

## Read output (non-destructive peek)

```powershell
# Read output without consuming it (Keep = $true)
Receive-Job -Name "myTask" -Keep
```

> Remove `-Keep` only when you want to consume and discard the buffered output.

---

## Wait for completion

```powershell
# Block until the job finishes (with timeout)
$job = Get-Job -Name "myTask"
$job | Wait-Job -Timeout 120   # seconds

if ($job.State -eq "Completed") {
    Receive-Job $job
} else {
    Write-Warning "Job did not finish in time. State: $($job.State)"
}
```

---

## Run multiple jobs in parallel

```powershell
$jobs = @(
    Start-Job -Name "task1" -ScriptBlock { python -u worker.py --id 1 },
    Start-Job -Name "task2" -ScriptBlock { python -u worker.py --id 2 },
    Start-Job -Name "task3" -ScriptBlock { python -u worker.py --id 3 }
)

# Wait for all
$jobs | Wait-Job

# Collect results
foreach ($j in $jobs) {
    Write-Host "=== $($j.Name) ==="
    Receive-Job $j
}
```

---

## Start a long-running server / process

```powershell
# Start server in background
$server = Start-Job -Name "devServer" -ScriptBlock {
    Set-Location $using:PWD
    python -m uvicorn app:app --reload --port 8000
}

# Poll until it is listening
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    $out = Receive-Job $server -Keep
    if ($out -match "Application startup complete") { break }
}
Write-Host "Server ready"
```

---

## Stop and clean up

```powershell
# Stop a specific job
Stop-Job -Name "myTask"

# Remove it from the session
Remove-Job -Name "myTask"

# Stop and remove all jobs at once
Get-Job | Stop-Job
Get-Job | Remove-Job
```

---

## Pass variables into a job

Use `$using:varName` to capture outer-scope variables inside `-ScriptBlock`:

```powershell
$workDir = "C:\projects\myapp"
$port    = 9000

$job = Start-Job -Name "app" -ScriptBlock {
    Set-Location $using:workDir
    python -m http.server $using:port
}
```

---

## Capture output to a file (for large logs)

```powershell
Start-Job -Name "bigJob" -ScriptBlock {
    python -u long_script.py *>&1 | Tee-Object -FilePath "C:\Temp\job.log"
}

# Tail the log from the main shell
Get-Content "C:\Temp\job.log" -Wait -Tail 30
```

---

## Tips

- Prefer `Start-Job` over `Start-Process -NoNewWindow` when you need to capture stdout/stderr.
- Use `-Keep` on `Receive-Job` while the job is still running so you don't lose buffered output.
- Clean up finished jobs with `Remove-Job` to avoid memory leaks in long sessions.
- For interactive programs that require a real TTY (e.g. full-screen TUIs), launch them directly in a new PowerShell window: `Start-Process powershell -ArgumentList "-NoExit", "-Command", "your-command"`.
- PowerShell jobs run in a child process; the working directory defaults to the user home. Always call `Set-Location $using:PWD` or pass an explicit path.
