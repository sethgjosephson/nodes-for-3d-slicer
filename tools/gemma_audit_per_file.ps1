<#
.SYNOPSIS
    Run a per-file audit prompt through Gemma and aggregate findings.

.DESCRIPTION
    Pattern: ask the same focused question of every file in a glob.
    Each call is small enough that the 8B model stays sharp and won't
    degenerate into repetition.  Aggregates findings to stdout.

.EXAMPLE
    pwsh tools/gemma_audit_per_file.ps1 `
        -Glob 'SlicerNodeEditor/NodeGraph/*.py' `
        -Prompt 'List every silently-swallowed exception (except blocks that pass or print only). One per line: <line> - <action>. Empty if none.'
#>
param(
    [Parameter(Mandatory=$true)]
    [string]$Glob,
    [Parameter(Mandatory=$true)]
    [string]$Prompt,
    [string]$Model       = 'gemma4:latest',
    [int]$NumCtx         = 16384,
    [int]$MaxTokens      = 600,
    [string]$Root        = (Get-Location).Path
)

$ErrorActionPreference = 'Stop'
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ask       = Join-Path $scriptDir 'ask_gemma.ps1'

$files = Get-ChildItem -Recurse -File -Path (Join-Path $Root $Glob) `
            | Where-Object { $_.Name -ne '__init__.py' }

foreach ($f in $files) {
    $rel = (Resolve-Path -LiteralPath $f.FullName -Relative)
    if ($rel.StartsWith('.\') -or $rel.StartsWith('./')) { $rel = $rel.Substring(2) }
    Write-Information "[gemma_audit] scanning $rel" -InformationAction Continue

    $resp = & $ask -Prompt $Prompt -Files $f.FullName `
                   -Model $Model -NumCtx $NumCtx -MaxTokens $MaxTokens 2>$null
    $resp = $resp.Trim()
    if (-not $resp -or $resp -eq 'NONE' -or $resp -eq 'None.' -or $resp -eq '(none)') {
        continue
    }
    Write-Output ('=== {0} ===' -f $rel)
    Write-Output $resp
    Write-Output ''
}
