# Script PowerShell per sincronizzare e testare Shibaclaw su WSL (Ubuntu)
Param(
    [switch]$Start
)

$wslDistro = "Ubuntu"
$wslUser = "rikyz"
$scriptPath = "/mnt/c/Users/Rikyz/.gemini/antigravity/scratch/shibaclaw_next/scripts/setup_wsl.sh"

Write-Host "🚀 Esecuzione sync e setup su WSL ($wslDistro, user $wslUser)..." -ForegroundColor Cyan

# Rende lo script eseguibile su Linux e lo lancia
wsl -d $wslDistro -u $wslUser bash -c "chmod +x $scriptPath && $scriptPath $(if ($Start) { '--start' })"
