# ShibaClaw Automated Installer for Windows
# This script installs Python (via winget), creates a venv, and installs shibaclaw via PyPI.

$ErrorActionPreference = "Stop"

[console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host ">> Starting ShibaClaw installation..." -ForegroundColor Cyan

# 1. Check/Install Python
$pyVersion = $null
$pythonCmd = $null

function Test-PythonCommand($cmd) {
    if (Get-Command $cmd -ErrorAction SilentlyContinue) {
        $out = & $cmd --version 2>&1
        if ($out -match "Python \d") { return $out }
    }
    return $null
}

$pyVersion = Test-PythonCommand "python"
if ($pyVersion) { $pythonCmd = "python" }
else {
    $pyVersion = Test-PythonCommand "py"
    if ($pyVersion) { $pythonCmd = "py" }
}

if ($null -eq $pyVersion) {
    Write-Host "[?] Python not found. Attempting to install via winget..." -ForegroundColor Yellow
    try {
        if (!(Get-Command winget -ErrorAction SilentlyContinue)) {
            Write-Error "winget is not installed. Please install Python 3.12+ manually from python.org"
            exit 1
        }
        winget install -e --id Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements
        Write-Host "[OK] Python installed successfully." -ForegroundColor Green

        $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")

        $pyVersion = Test-PythonCommand "python"
        if ($pyVersion) { $pythonCmd = "python" }
        else {
            $pyVersion = Test-PythonCommand "py"
            if ($pyVersion) { $pythonCmd = "py" }
        }

        if ($null -eq $pythonCmd) {
            Write-Host "[!] Python installed but not yet in PATH. Please restart your terminal and run this script again." -ForegroundColor Yellow
            exit 1
        }
    }
    catch {
        Write-Error "Failed to install Python via winget. Please install Python 3.12+ manually from python.org"
        exit 1
    }
}

Write-Host "[OK] Found Python: $pyVersion" -ForegroundColor Green

$installedVersion = & $pythonCmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>&1
if ([version]$installedVersion -lt [version]"3.12") {
    Write-Error "Python $installedVersion detected, but ShibaClaw requires Python 3.12+. Please upgrade from python.org"
    exit 1
}

# 2. Installation Method (Prefer pipx, fallback to venv+pip)
if (Get-Command pipx -ErrorAction SilentlyContinue) {
    Write-Host ">> pipx detected. Using pipx for a cleaner installation..." -ForegroundColor Cyan
    pipx install "shibaclaw[windows-native]"
    $shibaExec = "shibaclaw"
}
else {
    Write-Host ">> pipx not found. Falling back to manual venv + pip..." -ForegroundColor Cyan
    $installDir = "$HOME\.shibaclaw"
    $venvDir = "$installDir\venv"
    if (!(Test-Path $installDir)) {
        New-Item -ItemType Directory -Path $installDir | Out-Null
    }

    Write-Host ">> Creating virtual environment in $venvDir..." -ForegroundColor Cyan
    & $pythonCmd -m venv $venvDir

    Write-Host ">> Installing shibaclaw from PyPI..." -ForegroundColor Cyan
    & "$venvDir\Scripts\pip.exe" install --upgrade pip
    & "$venvDir\Scripts\pip.exe" install "shibaclaw[windows-native]"

    $scriptsPath = "$venvDir\Scripts"
    $currentPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
    if ($currentPath -notlike "*$scriptsPath*") {
        Write-Host ">> Adding ShibaClaw to User PATH..." -ForegroundColor Cyan
        [System.Environment]::SetEnvironmentVariable("Path", "$currentPath;$scriptsPath", "User")
        $env:Path += ";$scriptsPath"
    }
    $shibaExec = "$venvDir\Scripts\shibaclaw.exe"
}

$absExec = $shibaExec
if ($absExec -eq "shibaclaw") {
    $cmdPath = Get-Command shibaclaw -ErrorAction SilentlyContinue
    if ($cmdPath) {
        $absExec = $cmdPath.Source
    } else {
        $pipxDefault = "$HOME\.local\bin\shibaclaw.exe"
        if (Test-Path $pipxDefault) {
            $absExec = $pipxDefault
        }
    }
}

# Resolve shibaclaw-desktop.exe (gui-script: no console window)
$desktopExec = $null
$absExecDir = Split-Path $absExec -Parent
$desktopCandidate = Join-Path $absExecDir "shibaclaw-desktop.exe"
if (Test-Path $desktopCandidate) {
    $desktopExec = $desktopCandidate
} else {
    $cmdPath = Get-Command shibaclaw-desktop -ErrorAction SilentlyContinue
    if ($cmdPath) { $desktopExec = $cmdPath.Source }
}

if ($null -eq $desktopExec) {
    Write-Host "[!] shibaclaw-desktop.exe not found; shortcuts will use console mode." -ForegroundColor Yellow
    $desktopExec = $absExec
    $desktopArgs = "desktop"
} else {
    $desktopArgs = $null
}

Write-Host "[OK] Installation complete!" -ForegroundColor Green

Write-Host ">> Creating shortcuts on Desktop and Start Menu..." -ForegroundColor Cyan
try {
    $installDir = "$HOME\.shibaclaw"
    $assetsDir = "$installDir\assets"
    if (!(Test-Path $assetsDir)) {
        New-Item -ItemType Directory -Path $assetsDir | Out-Null
    }
    $icoPath = "$assetsDir\shibaclaw.ico"
    if (!(Test-Path $icoPath)) {
        Write-Host ">> Fetching ShibaClaw icon..." -ForegroundColor Cyan
        Invoke-WebRequest -Uri "https://raw.githubusercontent.com/RikyZ90/ShibaClaw/main/assets/shibaclaw.ico" -OutFile $icoPath -UseBasicParsing -ErrorAction SilentlyContinue
    }

    $WshShell = New-Object -ComObject WScript.Shell
    
    # Desktop shortcut
    $DesktopPath = [System.Environment]::GetFolderPath('Desktop')
    $Shortcut = $WshShell.CreateShortcut("$DesktopPath\ShibaClaw.lnk")
    $Shortcut.TargetPath = $desktopExec
    if ($desktopArgs) { $Shortcut.Arguments = $desktopArgs }
    if (Test-Path $icoPath) {
        $Shortcut.IconLocation = $icoPath
    }
    $Shortcut.Save()

    # Start Menu shortcut
    $StartMenuPath = [System.Environment]::GetFolderPath('Programs')
    $Shortcut2 = $WshShell.CreateShortcut("$StartMenuPath\ShibaClaw.lnk")
    $Shortcut2.TargetPath = $desktopExec
    if ($desktopArgs) { $Shortcut2.Arguments = $desktopArgs }
    if (Test-Path $icoPath) {
        $Shortcut2.IconLocation = $icoPath
    }
    $Shortcut2.Save()
} catch {
    Write-Host "[!] Failed to create shortcuts. You can still run 'shibaclaw' from your terminal." -ForegroundColor Yellow
}

Write-Host ">> Launching ShibaClaw..." -ForegroundColor Cyan

$env:PYTHONIOENCODING = "utf-8"
Start-Process $desktopExec -ArgumentList $desktopArgs
