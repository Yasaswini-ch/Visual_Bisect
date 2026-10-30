# Real-world case (n = 1): bisect a sidebar change in homow/dashboard-skeleton.
# Usage (from the repo root): powershell -File eval/real_case.ps1 <path-to-venv-python> [pixel-full|gemma]
# Needs GEMINI_API_KEY in .env for the gemma judge. Install scripts are disabled for the third-party repo.
param([string]$Python = "python", [string]$Judge = "gemma")
Set-Location (Split-Path $PSScriptRoot -Parent)
Get-Content .env -ErrorAction SilentlyContinue | ForEach-Object { $k, $v = $_ -split '=', 2; if ($k) { Set-Item "env:$k" $v } }
$repo = Join-Path $env:TEMP "vbcand\dashboard-skeleton"
if (-not (Test-Path $repo)) { git clone -q https://github.com/homow/dashboard-skeleton $repo }
& $Python -m vbisect.cli --repo $repo --good 4ce2f40 --bad 8fa9e4a --good-render `
    --focus "the left sidebar (layout, icons, text size, logo)" --judge $Judge `
    --install-cmd "npm ci --ignore-scripts" --out "runs/real/$Judge"
