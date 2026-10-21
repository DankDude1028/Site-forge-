[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Directory,
    [Parameter(Mandatory = $true)][string]$Archive,
    [Parameter(Mandatory = $true)][string]$KeyId,
    [Parameter(Mandatory = $true)][switch]$Disposable,
    [string]$Python = "python",
    [string]$PgBin,
    [ValidateRange(1, 3600)][int]$TimeoutSeconds = 600,
    [ValidateRange(1, 8589934592)][long]$MaxBytes = 536870912
)
$ErrorActionPreference = "Stop"
if (-not $Disposable) { throw "Restore requires -Disposable; existing databases are never overwritten." }
if (-not [IO.Path]::IsPathFullyQualified($Directory) -or -not [IO.Path]::IsPathFullyQualified($Archive)) {
    throw "Use explicit absolute backup directory and archive paths."
}
$repo = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $repo
try {
    $arguments = @("-m", "siteforge.backups", "restore", "--directory", $Directory,
        "--archive", $Archive, "--key-id", $KeyId, "--disposable", "--timeout", [string]$TimeoutSeconds,
        "--max-bytes", [string]$MaxBytes)
    if ($PgBin) { $arguments += @("--pg-bin", $PgBin) }
    & $Python @arguments
    if ($LASTEXITCODE -ne 0) { throw "Disposable restore failed; no production database was overwritten or promoted." }
} finally { Pop-Location }
