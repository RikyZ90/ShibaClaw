[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [switch]$Force,
    [string]$InstallDir
)

$ErrorActionPreference = "Stop"

$logPath = Join-Path $env:TEMP 'ShibaClaw-uninstall.log'
$hadErrors = $false

function Log-Message {
    param([string]$Message)
    $entry = "$(Get-Date -Format o) $Message"
    Add-Content -Path $logPath -Value $entry -Encoding utf8
}

function Resolve-ShibaClawInstallDir {
    param([string]$Override)

    if ($Override) {
        return [System.IO.Path]::GetFullPath($Override)
    }

    $candidates = @(
        $env:SHIBACLAW_INSTALL_DIR,
        $env:SHIBACLAW_HOME,
        $env:USERPROFILE,
        $env:HOME,
        $HOME
    ) | Where-Object { $_ -and $_.Trim() }

    foreach ($candidate in $candidates) {
        $candidatePath = [System.IO.Path]::GetFullPath($candidate)
        if ($candidatePath) {
            if ($candidatePath -match '[\\\/]\.shibaclaw$') {
                return $candidatePath
            }
            return (Join-Path $candidatePath ".shibaclaw")
        }
    }

    return [System.IO.Path]::GetFullPath((Join-Path ([Environment]::GetFolderPath("UserProfile")) ".shibaclaw"))
}

function Write-Step([string]$Message) {
    Write-Host ">> $Message" -ForegroundColor Cyan
}

function Write-Success([string]$Message) {
    Write-Host "[OK] $Message" -ForegroundColor Green
}

function Write-Warn([string]$Message) {
    Write-Host "[!] $Message" -ForegroundColor Yellow
}

function Confirm-Uninstall {
    if ($Force) { return $true }

    try {
        $answer = Read-Host "This will remove the ShibaClaw installation, shortcuts, and local app files. Continue? [y/N]"
        return $answer -match '^(y|yes)$'
    }
    catch {
        Log-Message "Confirm-Uninstall failed: $($_.Exception.Message)"
        return $false
    }
}

Write-Step "Starting ShibaClaw uninstall..."
Log-Message "Starting uninstall from $PWD"

if (-not (Confirm-Uninstall)) {
    Write-Warn "Uninstall cancelled."
    Log-Message "Uninstall cancelled by user or no prompt available."
    return
}

$installDir = Resolve-ShibaClawInstallDir -Override $InstallDir
Log-Message "Resolved install dir: $installDir"
$desktopPath = [Environment]::GetFolderPath('Desktop')
$startMenuPath = [Environment]::GetFolderPath('Programs')
$desktopShortcut = Join-Path $desktopPath "ShibaClaw.lnk"
$startMenuShortcut = Join-Path $startMenuPath "ShibaClaw.lnk"

# Remove pipx installation if present (legacy)
if (Get-Command pipx -ErrorAction SilentlyContinue) {
    Write-Step "Checking for pipx installation..."
    Log-Message "Attempting pipx uninstall"
    if ($PSCmdlet.ShouldProcess("pipx", "uninstall shibaclaw")) {
        try {
            & pipx uninstall shibaclaw 2>$null
            Log-Message "pipx uninstall completed"
        }
        catch {
            Log-Message "pipx uninstall skipped: $($_.Exception.Message)"
        }
    }
}

# Remove app directory (new layout) and venv (legacy layout)
$removeDirs = @(
    (Join-Path $installDir "app"),
    (Join-Path $installDir "venv")
)

$targets = @($desktopShortcut, $startMenuShortcut) + $removeDirs
foreach ($target in $targets) {
    if (Test-Path $target) {
        if ($PSCmdlet.ShouldProcess($target, "remove")) {
            try {
                Remove-Item -Path $target -Recurse -Force -ErrorAction Stop
                Log-Message "Removed: ${target}"
            }
            catch {
                Log-Message "Failed to remove ${target}: $($_.Exception.Message)"
            }
        }
    }
    else {
        Log-Message "Not found (skipped): $target"
    }
}

# Clean legacy executables from PATH-accessible locations
$commandsToRemove = @()
$shibaclawCommand = Get-Command shibaclaw -ErrorAction SilentlyContinue
if ($shibaclawCommand) { $commandsToRemove += $shibaclawCommand.Source }

$desktopCommand = Get-Command shibaclaw-desktop -ErrorAction SilentlyContinue
if ($desktopCommand) { $commandsToRemove += $desktopCommand.Source }

foreach ($commandPath in $commandsToRemove | Select-Object -Unique) {
    $userBinPattern = "${HOME}\.local\bin*"
    $installPattern = "${HOME}\.shibaclaw*"
    $venvPattern = "*\venv\Scripts\*"
    if ($commandPath -and ($commandPath -like $userBinPattern -or $commandPath -like $installPattern -or $commandPath -like $venvPattern)) {
        if ($PSCmdlet.ShouldProcess($commandPath, "remove executable")) {
            try {
                Remove-Item -Path $commandPath -Force -ErrorAction Stop
                Log-Message "Removed executable: ${commandPath}"
            }
            catch {
                Log-Message "Failed to remove executable ${commandPath}: $($_.Exception.Message)"
            }
        }
    }
}

# Clean PATH entries (both new app/ layout and legacy venv/ layout)
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath) {
    $shibaPatterns = @(
        (Join-Path $installDir "app\ShibaClaw"),
        (Join-Path $installDir "venv\Scripts")
    )
    $entries = $userPath -split ';' | Where-Object {
        $entry = $_
        $keep = $true
        foreach ($pat in $shibaPatterns) {
            if ($entry -eq $pat -or $entry -eq "$pat\") { $keep = $false; break }
        }
        $keep
    }
    $newPath = $entries -join ';'

    if ($newPath -ne $userPath) {
        if ($PSCmdlet.ShouldProcess("User PATH", "remove ShibaClaw entries")) {
            try {
                [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
                Log-Message "Cleaned ShibaClaw entries from user PATH"
            }
            catch {
                Log-Message "Failed to update user PATH: $($_.Exception.Message)"
            }
        }
    }
}

# Remove registry uninstall entry
$registryKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\ShibaClaw'
if (Test-Path $registryKey) {
    if ($PSCmdlet.ShouldProcess($registryKey, "remove uninstall registry entry")) {
        try {
            Remove-Item -Path $registryKey -Recurse -Force -ErrorAction Stop
            Log-Message "Removed uninstall registry entry"
        }
        catch {
            Log-Message "Failed to remove uninstall registry entry: $($_.Exception.Message)"
        }
    }
}

# Clean up install.log
$installLog = Join-Path $installDir "install.log"
Remove-Item -Path $installLog -Force -ErrorAction SilentlyContinue

Write-Success "ShibaClaw has been removed."
Write-Host "Please close and reopen your terminal to refresh PATH."
Log-Message "Uninstall completed."
