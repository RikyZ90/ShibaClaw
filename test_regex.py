import re

deny = [
    r"\brm\s+-[rf]{1,2}\b",
    r"\bdel\s+/[fq]\b",
    r"\brmdir\s+/s\b",
    r"(?:^|[;&|]\s*)format\b(?!-)",
    r"\b(mkfs|diskpart)\b",
    r"\bdd\s+if=",
    r">\s*/dev/sd",
    r"\b(shutdown|reboot|poweroff)\b",
    r":\(\)\s*\{.*\};\s*:",
    r"\b(eval|alias)\b",
    r"\bsudo\s+",
    r"\b(nc|netcat|ncat)\b",
    r"\b(bash|sh|zsh|dash)\s+-i\b",
    r"\$\([^)]*\)",
    r"`[^`]*`",
    r"\|\s*(sh|bash|zsh|dash|fish)\b",
    r"\b(apt|apt-get|yum|dnf|brew)\s+(remove|purge)\b",
    r"\bpip3?\s+(uninstall)\b",
    r"\b(npm|yarn|pnpm)\s+(remove|uninstall)\b",
    r"\b(curl|wget)\b.*\|\s*(sh|bash|zsh|dash)\b",
    r"<\([^)]*\)",
    r"\bInvoke-Expression\b",
    r"\biex\b",
    r"\bSet-ExecutionPolicy\b",
    r"\bInvoke-WebRequest\b.*\|.*powershell",
    r"\bStart-Process\b.*-Verb\s+RunAs",
]

cmd = "Get-Process | Sort-Object CPU -Descending | Select-Object -First 15 Name, CPU, WorkingSet | Format-Table -AutoSize; `n`nWrite-Host \"--- PROGRAMMI ALL'AVVIO ---\"; `nGet-CimInstance Win32_StartupCommand | Select-Object Name, Command, Location | Format-Table -AutoSize"

for p in deny:
    if re.search(p, cmd.lower()):
        print(f"MATCH: {p}")
