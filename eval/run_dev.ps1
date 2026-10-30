# Runs the dev eval detached from any terminal timeout and logs to eval_<label>.log.
# Usage (from the repo root): powershell -File eval/run_dev.ps1 <path-to-venv-python> [label]
param([string]$Python = "python", [string]$Label = "dev")
Set-Location (Split-Path $PSScriptRoot -Parent)
Get-Content .env | ForEach-Object { $k, $v = $_ -split '=', 2; if ($k) { Set-Item "env:$k" $v } }
$env:PATH = (Split-Path $Python -Parent) + ";" + $env:PATH
$log = "eval_$Label.log"
& $Python eval/run_eval.py --cases eval/cases --seeds 1 2 3 4 5 6 7 8 --judges gemma pixel-crop pixel-full `
    --workers 2 --label $Label --out "eval/results.$Label.json" *> $log
& $Python eval/summarize.py "eval/results.$Label.json" *>> $log
"finished" | Add-Content $log
