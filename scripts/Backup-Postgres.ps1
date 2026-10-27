[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Directory,
    [Parameter(Mandatory = $true)][string]$KeyId,
    [string]$Python = "python",
    [string]$PgBin,
    [ValidateRange(1, 3650)][int]$RetainDays = 30,
    [ValidateRange(1, 1000)][int]$Keep = 7,
    [ValidateRange(1, 3600)][int]$TimeoutSeconds = 600,
    [ValidateRange(1, 8589934592)][long]$MaxBytes = 536870912
)
$ErrorActionPreference = "Stop"
if (-not [IO.Path]::IsPathFullyQualified($Directory)) { throw "Use an absolute backup directory." }
$repo = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $repo
try {
    $arguments = @("-m", "siteforge.backups", "backup", "--directory", $Directory,
        "--key-id", $KeyId, "--timeout", [string]$TimeoutSeconds, "--max-bytes", [string]$MaxBytes)
    if ($PgBin) { $arguments += @("--pg-bin", $PgBin) }
    # Credentials/key are read only from environment by Python, never interpolated.
    & $Python @arguments
    if ($LASTEXITCODE -ne 0) { throw "Encrypted backup failed. No retention was attempted." }
    & $Python -m siteforge.backups retain --directory $Directory --key-id $KeyId --days $RetainDays --keep $Keep --max-bytes $MaxBytes
    if ($LASTEXITCODE -ne 0) { throw "Backup was written but local retention failed; inspect operator evidence." }
} finally { Pop-Location }
