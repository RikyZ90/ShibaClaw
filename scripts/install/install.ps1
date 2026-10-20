[CmdletBinding()]
param(
    [string]$Version = "",
    [string]$InstallDir = "",
    [string]$LocalSetupPath = "",
    [string]$SetupSha256 = "",
    [string]$LocalZipPath = ""
)

$ErrorActionPreference = "Stop"

function Get-ShibaClawSetupAsset {
    param([Parameter(Mandatory = $true)]$Release)

    $assets = @($Release.assets | Where-Object { $_.name -ceq "ShibaClaw-Setup.exe" })
    if ($assets.Count -ne 1) {
        throw "Release does not contain exactly one ShibaClaw-Setup.exe. Use a release with the Windows setup artifact."
    }
    $asset = $assets[0]
    if ([string]$asset.digest -notmatch '^sha256:[0-9a-fA-F]{64}$') {
        throw "GitHub did not provide a SHA256 digest for ShibaClaw-Setup.exe. Refusing to run an unverified download."
    }
    $uri = [Uri]$asset.browser_download_url
    if ($uri.Scheme -ne 'https' -or $uri.Host -ne 'github.com' -or
        $uri.AbsolutePath -notlike '/RikyZ90/ShibaClaw/releases/download/*/ShibaClaw-Setup.exe') {
        throw "Unexpected setup download URL in GitHub release metadata."
    }
    return $asset
}

function Assert-ShibaClawSetupHash {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$ExpectedSha256
    )

    if ($ExpectedSha256 -notmatch '^[0-9a-fA-F]{64}$') {
        throw "A valid SHA256 digest is required before setup can run."
    }
    $actual = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash
    if ($actual -ine $ExpectedSha256) {
        throw "Setup SHA256 verification failed. The downloaded file will not be executed."
    }
}

function Get-ShibaClawSetupArguments {
    param([string]$Destination)

    if (-not $Destination) { return @() }
    $destinationPath = [IO.Path]::GetFullPath($Destination)
    if ($destinationPath.Contains('"')) { throw 'InstallDir cannot contain a quote.' }
    # Keep mutable app data outside the directory managed (and uninstalled) by Velopack.
    $destinationRoot = $destinationPath.TrimEnd([IO.Path]::DirectorySeparatorChar)
    $prefix = $destinationRoot + [IO.Path]::DirectorySeparatorChar
    $homeCandidates = @([Environment]::GetFolderPath('UserProfile'), $env:USERPROFILE, $env:HOME, $HOME)
    foreach ($homeCandidate in ($homeCandidates | Where-Object { $_ } | Select-Object -Unique)) {
        $dataPath = [IO.Path]::GetFullPath((Join-Path $homeCandidate '.shibaclaw')).TrimEnd([IO.Path]::DirectorySeparatorChar)
        $dataPrefix = $dataPath + [IO.Path]::DirectorySeparatorChar
        if ($dataPath.Equals($destinationRoot, [StringComparison]::OrdinalIgnoreCase) -or
            $dataPath.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase) -or
            $destinationRoot.StartsWith($dataPrefix, [StringComparison]::OrdinalIgnoreCase)) {
            throw 'InstallDir must be separate from .shibaclaw user data. Leave -InstallDir empty when migrating; existing data will be preserved.'
        }
    }
    # Start-Process joins ArgumentList; quote Windows paths and escape a trailing backslash.
    $quoted = '"' + [regex]::Replace($destinationPath, '(\\+)$', '$1$1') + '"'
    return @('--installto', $quoted)
}

function Install-ShibaClawSetup {
    param(
        [string]$RequestedVersion = "",
        [string]$Destination = "",
        [string]$LocalPath = "",
        [string]$LocalSha256 = "",
        [string]$LegacyZipPath = ""
    )

    if ($LegacyZipPath) {
        if ($LocalPath) { throw 'LocalZipPath and LocalSetupPath cannot be combined.' }
        # Old EXE updaters pass a downloaded ZIP and the combined app/data root.
        # Treat that ZIP only as a migration signal: never read, execute or remove it.
        $Destination = ""
        Write-Warning 'Legacy ZIP updater detected. The verified Windows setup will use its default application directory (%LocalAppData%\ShibaClaw). Configuration and conversations stay in .shibaclaw; legacy files and the ZIP are left untouched.'
    }
    $setupArguments = @(Get-ShibaClawSetupArguments -Destination $Destination)
    if ($RequestedVersion -and $RequestedVersion -notmatch '^v?\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$') {
        throw 'Version must be a release version such as 1.1.1 or v1.1.1.'
    }
    $downloadUrl = $null
    $expectedHash = $LocalSha256
    if ($LocalPath) {
        if (-not (Test-Path -LiteralPath $LocalPath -PathType Leaf)) { throw 'LocalSetupPath does not exist.' }
        if ($expectedHash -notmatch '^[0-9a-fA-F]{64}$') {
            throw 'LocalSetupPath requires -SetupSha256 with the trusted expected SHA256 digest.'
        }
    } else {
        # Windows PowerShell 5.1 needs TLS 1.2 enabled explicitly on older systems.
        [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
        $apiUrl = 'https://api.github.com/repos/RikyZ90/ShibaClaw/releases/latest'
        if ($RequestedVersion) {
            $tag = if ($RequestedVersion.StartsWith('v')) { $RequestedVersion } else { 'v' + $RequestedVersion }
            $apiUrl = 'https://api.github.com/repos/RikyZ90/ShibaClaw/releases/tags/' + [Uri]::EscapeDataString($tag)
        }
        Write-Host 'Fetching ShibaClaw Windows setup release...'
        $release = Invoke-RestMethod -Uri $apiUrl -Headers @{ Accept = 'application/vnd.github+json' } -UseBasicParsing
        $asset = Get-ShibaClawSetupAsset -Release $release
        $downloadUrl = $asset.browser_download_url
        $expectedHash = $asset.digest.Substring(7)
    }

    $temporaryRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
    $temporaryDir = Join-Path $temporaryRoot ('ShibaClaw-setup-' + [Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $temporaryDir -ErrorAction Stop | Out-Null
    try {
        $setupPath = Join-Path $temporaryDir 'ShibaClaw-Setup.exe'
        if ($LocalPath) {
            Copy-Item -LiteralPath $LocalPath -Destination $setupPath
        } else {
            Write-Host 'Downloading ShibaClaw-Setup.exe...'
            Invoke-WebRequest -Uri $downloadUrl -OutFile $setupPath -UseBasicParsing
        }
        Assert-ShibaClawSetupHash -Path $setupPath -ExpectedSha256 $expectedHash
        Write-Host 'SHA256 integrity verified. Starting Windows setup...'
        $start = @{ FilePath = $setupPath; PassThru = $true; ErrorAction = 'Stop' }
        if ($setupArguments.Count) { $start.ArgumentList = $setupArguments }
        $process = Start-Process @start
        if ($null -eq $process) { throw 'Windows setup did not return a process handle.' }
        # Start-Process -Wait also waits for descendants, including the launched
        # desktop app. Await only setup so the terminal returns after installation.
        $process.WaitForExit()
        $process.Refresh()
        if ($process.ExitCode -ne 0) {
            throw "ShibaClaw setup failed with exit code $($process.ExitCode)."
        }
        Write-Host 'ShibaClaw setup completed. Existing configuration and conversations were preserved.'
    } finally {
        # Remove only the unique temporary directory created by this invocation.
        $resolvedTemp = [IO.Path]::GetFullPath($temporaryDir)
        $tempPrefix = $temporaryRoot.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
        if (-not $resolvedTemp.StartsWith($tempPrefix, [StringComparison]::OrdinalIgnoreCase)) {
            throw 'Refusing to clean a path outside the temporary directory.'
        }
        Remove-Item -LiteralPath $resolvedTemp -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Install-ShibaClawSetup -RequestedVersion $Version -Destination $InstallDir -LocalPath $LocalSetupPath -LocalSha256 $SetupSha256 -LegacyZipPath $LocalZipPath
