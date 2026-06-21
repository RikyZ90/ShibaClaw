# ShibaClaw Automated Installer for Windows
# Downloads the latest pre-built release from GitHub and sets up shortcuts.

$ErrorActionPreference = "Stop"

[console]::OutputEncoding = [System.Text.Encoding]::UTF8

$installDir = "$HOME\.shibaclaw"
$appDir     = "$installDir\app"
$shibaDir   = "$appDir\ShibaClaw"
$shibaExe   = "$shibaDir\ShibaClaw.exe"

if (!(Test-Path $installDir)) {
    New-Item -ItemType Directory -Path $installDir -Force | Out-Null
}
$installLog = Join-Path $installDir "install.log"

function Show-InstallProgress {
    param(
        [Parameter(Mandatory = $true)][string]$Message,
        [Parameter(Mandatory = $true)][int]$Step,
        [Parameter(Mandatory = $true)][int]$Total,
        [string]$Detail = ""
    )

    $percent = [Math]::Min(100, [int](($Step / $Total) * 100))
    $status = if ($Detail) { "$Message - $Detail" } else { $Message }
    Write-Progress -Activity "ShibaClaw installation" -Status $status -PercentComplete $percent
    Write-Host ("[{0}/{1}] {2}" -f $Step, $Total, $status) -ForegroundColor Cyan
}

function Invoke-LoggedStep {
    param(
        [Parameter(Mandatory = $true)][string]$Message,
        [Parameter(Mandatory = $true)][int]$Step,
        [Parameter(Mandatory = $true)][int]$Total,
        [Parameter(Mandatory = $true)][scriptblock]$Action
    )

    Show-InstallProgress -Message $Message -Step $Step -Total $Total

    try {
        & $Action 2>&1 | Out-File -FilePath $installLog -Append -Encoding utf8
        if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) {
            throw "Step failed: $Message"
        }
    }
    catch {
        if (Test-Path $installLog) {
            Write-Host "[!] Installation details were saved to $installLog" -ForegroundColor Yellow
        }
        throw
    }
}

if (Test-Path $installLog) {
    Remove-Item $installLog -Force
}

Write-Host ">> Starting ShibaClaw installation..." -ForegroundColor Cyan

# ── 1. Resolve latest release from GitHub ────────────────────────────────────

Show-InstallProgress -Message "Fetching latest release info..." -Step 1 -Total 6

$apiUrl = "https://api.github.com/repos/RikyZ90/ShibaClaw/releases/latest"
try {
    $releaseInfo = Invoke-RestMethod -Uri $apiUrl -UseBasicParsing -Headers @{ Accept = "application/vnd.github+json" }
}
catch {
    Write-Error "Failed to fetch latest release from GitHub. Check your internet connection and try again."
    exit 1
}

$tagName = $releaseInfo.tag_name
$displayVersion = $tagName -replace '^v', ''

$asset = $releaseInfo.assets | Where-Object { $_.name -eq "ShibaClaw-windows.zip" } | Select-Object -First 1
if ($null -eq $asset) {
    Write-Error "Could not find ShibaClaw-windows.zip in release $tagName. The release may not include a Windows build yet."
    exit 1
}

$downloadUrl = $asset.browser_download_url
Write-Host "[OK] Found release $tagName" -ForegroundColor Green

# ── 2. Download the zip ──────────────────────────────────────────────────────

$zipPath = Join-Path $env:TEMP "ShibaClaw-windows.zip"

Invoke-LoggedStep -Message "Downloading ShibaClaw $tagName..." -Step 2 -Total 6 -Action {
    Invoke-WebRequest -Uri $downloadUrl -OutFile $zipPath -UseBasicParsing
}

Write-Host "[OK] Download complete." -ForegroundColor Green

# ── 3. Extract and unblock ───────────────────────────────────────────────────

Invoke-LoggedStep -Message "Extracting files..." -Step 3 -Total 6 -Action {
    if (Test-Path $appDir) {
        Remove-Item -Path $appDir -Recurse -Force
    }
    New-Item -ItemType Directory -Path $appDir -Force | Out-Null
    Expand-Archive -Path $zipPath -DestinationPath $appDir -Force
}

Remove-Item -Path $zipPath -Force -ErrorAction SilentlyContinue

if (!(Test-Path $shibaExe)) {
    $nested = Get-ChildItem -Path $appDir -Filter "ShibaClaw.exe" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($nested) {
        $shibaDir = $nested.DirectoryName
        $shibaExe = $nested.FullName
    }
    else {
        Write-Error "ShibaClaw.exe not found after extraction. The archive may be corrupted."
        exit 1
    }
}

Get-ChildItem -Path $shibaDir -Recurse -Include '*.exe', '*.dll' | Unblock-File

Write-Host "[OK] Extracted to $shibaDir" -ForegroundColor Green

# ── 4. Add to PATH ──────────────────────────────────────────────────────────

Show-InstallProgress -Message "Configuring PATH..." -Step 4 -Total 6

$currentPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
if ($currentPath -notlike "*$shibaDir*") {
    [System.Environment]::SetEnvironmentVariable("Path", "$currentPath;$shibaDir", "User")
    $env:Path += ";$shibaDir"
    Write-Host "[OK] Added ShibaClaw to User PATH." -ForegroundColor Green
}

# ── 5. Shortcuts + uninstall registration ────────────────────────────────────

Show-InstallProgress -Message "Creating shortcuts..." -Step 5 -Total 6

$uninstallScript = Join-Path $installDir "uninstall.ps1"

# ── Write embedded uninstall script ──────────────────────────────────────────

$uninstallContent = @'
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [switch]$Force,
    [string]$InstallDir
)

$ErrorActionPreference = "Stop"

$logPath = Join-Path $env:TEMP 'ShibaClaw-uninstall.log'

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
$desktopShortcut = Join-Path ([Environment]::GetFolderPath('Desktop')) "ShibaClaw.lnk"
$startMenuShortcut = Join-Path ([Environment]::GetFolderPath('Programs')) "ShibaClaw.lnk"

# Remove pipx installation if present (legacy)
if (Get-Command pipx -ErrorAction SilentlyContinue) {
    Write-Step "Checking for pipx installation..."
    Log-Message "Attempting pipx uninstall"
    try {
        pipx uninstall shibaclaw -q 2>$null
        Log-Message "pipx uninstall completed"
    }
    catch {
        Log-Message "pipx uninstall skipped: $($_.Exception.Message)"
    }
}

# Remove app directory (new layout) and venv (legacy layout)
$removeDirs = @(
    (Join-Path $installDir "app"),
    (Join-Path $installDir "venv")
)

foreach ($target in @($desktopShortcut, $startMenuShortcut) + $removeDirs) {
    if (Test-Path $target) {
        try {
            Remove-Item -Path $target -Recurse -Force -ErrorAction Stop
            Log-Message "Removed: ${target}"
        }
        catch {
            Log-Message "Failed to remove ${target}: $($_.Exception.Message)"
        }
    }
    else {
        Log-Message "Not found (skipped): ${target}"
    }
}

# Clean PATH entries
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath) {
    $shibaPatterns = @(
        (Join-Path $installDir "app\ShibaClaw"),
        (Join-Path $installDir "app\ShibaClaw\"),
        (Join-Path $installDir "venv\Scripts"),
        (Join-Path $installDir "venv\Scripts\")
    )
    $entries = $userPath -split ';' | Where-Object {
        $entry = $_
        $keep = $true
        foreach ($pat in $shibaPatterns) {
            if ($entry -eq $pat) { $keep = $false; break }
        }
        $keep
    }
    $newPath = $entries -join ';'

    if ($newPath -ne $userPath) {
        try {
            [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
            Log-Message "Cleaned ShibaClaw entries from user PATH"
        }
        catch {
            Log-Message "Failed to update user PATH: $($_.Exception.Message)"
        }
    }
}

# Remove registry uninstall entry
$registryKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\ShibaClaw'
if (Test-Path $registryKey) {
    try {
        Remove-Item -Path $registryKey -Recurse -Force -ErrorAction Stop
        Log-Message "Removed uninstall registry entry"
    }
    catch {
        Log-Message "Failed to remove uninstall registry entry: $($_.Exception.Message)"
    }
}

# Remove install.log and uninstall script itself
$selfPath = $MyInvocation.MyCommand.Path
$installLog = Join-Path $installDir "install.log"
Remove-Item -Path $installLog -Force -ErrorAction SilentlyContinue

Write-Success "ShibaClaw has been removed."
Write-Host "Please close and reopen your terminal to refresh PATH."
Log-Message "Uninstall completed."
'@

$uninstallContent | Set-Content -Path $uninstallScript -Encoding UTF8 -Force

# ── Register in Apps & Features ──────────────────────────────────────────────

try {
    $appKeyPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\ShibaClaw"
    $uninstallCommand = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$uninstallScript`" -Force -InstallDir `"$installDir`""

    New-Item -Path $appKeyPath -Force | Out-Null
    New-ItemProperty -Path $appKeyPath -Name "DisplayName"          -Value "ShibaClaw"           -PropertyType String -Force | Out-Null
    New-ItemProperty -Path $appKeyPath -Name "DisplayVersion"       -Value $displayVersion       -PropertyType String -Force | Out-Null
    New-ItemProperty -Path $appKeyPath -Name "Publisher"             -Value "RikyZ90"             -PropertyType String -Force | Out-Null
    New-ItemProperty -Path $appKeyPath -Name "InstallLocation"      -Value $shibaDir             -PropertyType String -Force | Out-Null
    New-ItemProperty -Path $appKeyPath -Name "UninstallString"      -Value $uninstallCommand     -PropertyType String -Force | Out-Null
    New-ItemProperty -Path $appKeyPath -Name "QuietUninstallString" -Value $uninstallCommand     -PropertyType String -Force | Out-Null
    New-ItemProperty -Path $appKeyPath -Name "DisplayIcon"          -Value "$shibaExe,0"         -PropertyType String -Force | Out-Null
    New-ItemProperty -Path $appKeyPath -Name "NoModify"             -Value 1                     -PropertyType DWord  -Force | Out-Null
    New-ItemProperty -Path $appKeyPath -Name "NoRepair"             -Value 1                     -PropertyType DWord  -Force | Out-Null
    New-ItemProperty -Path $appKeyPath -Name "EstimatedSize"        -Value 1024                  -PropertyType DWord  -Force | Out-Null
    New-ItemProperty -Path $appKeyPath -Name "URLInfoAbout"         -Value "https://github.com/RikyZ90/ShibaClaw" -PropertyType String -Force | Out-Null

    Write-Host "[OK] Registered in Apps & Features." -ForegroundColor Green
}
catch {
    Write-Warning "Could not register uninstall entry: $($_.Exception.Message)"
}

# ── Create shortcuts ─────────────────────────────────────────────────────────

try {
    $WshShell = New-Object -ComObject WScript.Shell

    $DesktopPath = [System.Environment]::GetFolderPath('Desktop')
    $lnkDesktop = "$DesktopPath\ShibaClaw.lnk"
    $Shortcut = $WshShell.CreateShortcut($lnkDesktop)
    $Shortcut.TargetPath = $shibaExe
    $Shortcut.WorkingDirectory = $shibaDir
    $Shortcut.IconLocation = "$shibaExe,0"
    $Shortcut.Save()

    $StartMenuPath = [System.Environment]::GetFolderPath('Programs')
    $lnkStartMenu = "$StartMenuPath\ShibaClaw.lnk"
    $Shortcut2 = $WshShell.CreateShortcut($lnkStartMenu)
    $Shortcut2.TargetPath = $shibaExe
    $Shortcut2.WorkingDirectory = $shibaDir
    $Shortcut2.IconLocation = "$shibaExe,0"
    $Shortcut2.Save()

    Write-Host "[OK] Shortcuts created (Desktop + Start Menu)." -ForegroundColor Green
}
catch {
    Write-Host "[!] Failed to create shortcuts. You can still run ShibaClaw.exe directly from $shibaDir" -ForegroundColor Yellow
}

# ── 6. Launch ────────────────────────────────────────────────────────────────

Show-InstallProgress -Message "Launching ShibaClaw..." -Step 6 -Total 6

Start-Process $shibaExe

Write-Progress -Activity "ShibaClaw installation" -Completed
Write-Host ""
Write-Host "[OK] Installation complete! ShibaClaw $tagName is ready." -ForegroundColor Green
Write-Host "     You can also launch it from your Desktop shortcut or Start Menu." -ForegroundColor Gray
