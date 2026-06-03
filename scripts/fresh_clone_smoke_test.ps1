param(
    [string]$RepoPath = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [switch]$RunSetup
)

$ErrorActionPreference = "Stop"
$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("forjyn-fresh-clone-" + [System.Guid]::NewGuid().ToString("N"))
$clonePath = Join-Path $tempRoot "forjyn"

New-Item -ItemType Directory -Path $tempRoot | Out-Null
try {
    git clone --no-local $RepoPath $clonePath | Out-Host
    Push-Location $clonePath
    try {
        git status --short | Out-Host
        if (-not (Test-Path "setup_windows.bat")) { throw "setup_windows.bat missing" }
        if (-not (Test-Path "run_forjyn_workbench.bat")) { throw "run_forjyn_workbench.bat missing" }
        if (-not (Test-Path "requirements.txt")) { throw "requirements.txt missing" }
        if (-not (Test-Path "tools\forjyn_paths.py")) { throw "tools\forjyn_paths.py missing" }
        if (-not (Test-Path ".github\workflows\ci.yml")) { throw ".github\workflows\ci.yml missing" }
        git ls-files workbench .venv | Out-Host
        if ($RunSetup) {
            cmd /c setup_windows.bat
            if ($LASTEXITCODE -ne 0) { throw "setup_windows.bat failed with exit code $LASTEXITCODE" }
        }
        Write-Host "Fresh clone smoke check passed."
    }
    finally {
        Pop-Location
    }
}
finally {
    if (Test-Path $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force
    }
}
