# PowerShell mirror of the Makefile targets: .\tasks.ps1 <data|eval|test>
param([Parameter(Mandatory = $true)][ValidateSet("data", "eval", "test")][string]$Target)

switch ($Target) {
    "data" { uv run python eval/make_cases.py --all }
    "eval" { uv run python eval/run_all.py; if ($?) { uv run python eval/score.py } }
    "test" { uv run pytest }
}
