param([string]$Python = 'python')
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $taskRoot
try {
  $bundledPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
  if ($Python -eq 'python' -and (Test-Path -LiteralPath $bundledPython)) { $Python = $bundledPython }
  if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) { & $Python -m venv .venv; if ($LASTEXITCODE) { throw 'Python 3.12+ is required.' } }
  & .\.venv\Scripts\python.exe -m pip install -r requirements.lock
  if ($LASTEXITCODE) { throw 'Dependency installation failed.' }
  & .\.venv\Scripts\python.exe -m pip install --no-deps -e .
  if ($LASTEXITCODE) { throw 'Editable installation failed.' }
  Write-Output 'Installed. See README.md for initialization and secret configuration.'
} finally { Pop-Location }
