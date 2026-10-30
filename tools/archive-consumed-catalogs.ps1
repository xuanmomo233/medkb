param(
    [Parameter(Mandatory=$true)][string]$PlanPath,
    [switch]$Apply,
    [string]$Python = 'python'
)
$ErrorActionPreference = 'Stop'
$OutputEncoding = [Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
[Console]::InputEncoding = [Text.UTF8Encoding]::new($false)
$PSDefaultParameterValues['*:Encoding'] = 'utf8NoBOM'
if ($PSVersionTable.PSVersion.Major -lt 7) { throw 'PowerShell 7 required' }

$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$workRoot = (Resolve-Path -LiteralPath (Join-Path $root 'work')).Path
$planFile = (Resolve-Path -LiteralPath $PlanPath).Path
if (-not $planFile.StartsWith($workRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Plan must be inside workspace work directory'
}
$executor = Join-Path $PSScriptRoot 'archive-consumed-catalogs.py'
$arguments = @('-X', 'utf8', $executor, '--plan', $planFile)
if ($Apply) { $arguments += '--apply' }
& $Python @arguments
if ($LASTEXITCODE -ne 0) { throw "Archive executor failed with exit code $LASTEXITCODE" }
