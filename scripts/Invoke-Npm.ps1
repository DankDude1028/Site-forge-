param([Parameter(ValueFromRemainingArguments = $true)][string[]]$NpmArguments)
$ErrorActionPreference = 'Stop'
$nodePath = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe'
if (-not (Test-Path -LiteralPath $nodePath)) { $nodePath = (Get-Command node -ErrorAction Stop).Source }
$nodeVersion = & $nodePath -p 'process.versions.node'
if ([version]$nodeVersion -lt [version]'22.23.4') { throw 'Astro requires Node 22.23.4+; configure a current Node runtime.' }
$npmCommand = Get-Command npm -ErrorAction Stop
$npmCli = Join-Path (Split-Path -Parent $npmCommand.Source) 'node_modules\npm\bin\npm-cli.js'
if (-not (Test-Path -LiteralPath $npmCli)) { throw 'Cannot locate npm-cli.js beside the installed npm command.' }
$env:PATH = (Split-Path -Parent $nodePath) + [IO.Path]::PathSeparator + $env:PATH
& $nodePath $npmCli @NpmArguments
if ($LASTEXITCODE) { throw "npm failed with exit code $LASTEXITCODE" }
