# Copies the latest catalog into the Android app's assets (the offline fallback bundled in the APK).
#
# 1. If a catalog base URL is configured, download index.json, changes.json and every city file.
# 2. Otherwise (or if the download fails) copy from pipeline\output\catalog\.
# 3. If neither is available, keep whatever is already in the assets folder.
#
# The base URL comes from $env:OPENNAKSHA_CATALOG_URL, or else `opennaksha.catalogBaseUrl` in
# android\gradle.properties (e.g. https://<user>.github.io/<repo>).
$ErrorActionPreference = 'Stop'

$Root  = Split-Path -Parent $PSScriptRoot
$Dest  = Join-Path $Root 'android\app\src\main\assets\catalog'
$Local = Join-Path $Root 'pipeline\output\catalog'

$base = $env:OPENNAKSHA_CATALOG_URL
$props = Join-Path $Root 'android\gradle.properties'
if (-not $base -and (Test-Path $props)) {
    $line = Get-Content $props | Where-Object { $_ -match '^opennaksha\.catalogBaseUrl=' } | Select-Object -First 1
    if ($line) { $base = $line.Substring($line.IndexOf('=') + 1).Trim() }
}
if ($base) { $base = $base.TrimEnd('/') }

function Sync-Remote {
    $tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("opennaksha-" + [guid]::NewGuid())
    New-Item -ItemType Directory -Force (Join-Path $tmp 'cities') | Out-Null
    try {
        Write-Host "Downloading catalog from $base/catalog/ ..."
        Invoke-WebRequest -UseBasicParsing -TimeoutSec 60 -Uri "$base/catalog/index.json" -OutFile (Join-Path $tmp 'index.json')
        try {
            Invoke-WebRequest -UseBasicParsing -TimeoutSec 60 -Uri "$base/catalog/changes.json" -OutFile (Join-Path $tmp 'changes.json')
        } catch { }
        $index = Get-Content -Raw (Join-Path $tmp 'index.json') | ConvertFrom-Json
        foreach ($city in $index.cities) {
            Invoke-WebRequest -UseBasicParsing -TimeoutSec 120 -Uri "$base/catalog/cities/$($city.id).json" `
                -OutFile (Join-Path $tmp "cities\$($city.id).json")
        }
        if (Test-Path $Dest) { Remove-Item -Recurse -Force $Dest }
        New-Item -ItemType Directory -Force $Dest | Out-Null
        Copy-Item -Recurse -Force (Join-Path $tmp '*') $Dest
        return $true
    } catch {
        Write-Warning "Download failed: $_"
        return $false
    } finally {
        Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
    }
}

if ($base -and (Sync-Remote)) {
    Write-Host "Bundled catalog updated from $base"
} elseif (Test-Path (Join-Path $Local 'index.json')) {
    Write-Host "Copying local pipeline output from $Local"
    if (Test-Path $Dest) { Remove-Item -Recurse -Force $Dest }
    New-Item -ItemType Directory -Force $Dest | Out-Null
    Copy-Item -Recurse -Force (Join-Path $Local '*') $Dest
} else {
    Write-Warning "No published catalog and no pipeline\output\catalog found; keeping existing assets."
    Write-Warning "Run the pipeline first:  cd pipeline; uv run python -m opennaksha.run"
}
