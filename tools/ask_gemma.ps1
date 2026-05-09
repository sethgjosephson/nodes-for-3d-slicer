<#
.SYNOPSIS
    Send a prompt (and optional files) to a local Ollama-hosted Gemma model.

.DESCRIPTION
    Reads each file LOCALLY and stuffs its content into the prompt sent
    to Ollama's /api/generate endpoint.  The file content never enters
    Claude's context — only the model's response (printed to stdout)
    does.  Used to offload token-heavy analysis to local hardware.

.PARAMETER Prompt
    The instruction for the model.  Use plain text or a multi-line
    here-string.

.PARAMETER Files
    One or more paths.  Each is read with Get-Content -Raw and appended
    to the prompt under a "--- FILE: <path> ---" delimiter.

.PARAMETER Model
    Ollama model tag (default: gemma4:latest — the smaller 8B model).
    Use gemma4:31b for harder analysis at the cost of throughput.

.PARAMETER MaxTokens
    Cap on response length (default: 4096).

.PARAMETER System
    Optional system prompt (Ollama "system" field).

.PARAMETER Format
    Optional output format ("json" forces JSON-mode generation).

.EXAMPLE
    pwsh tools/ask_gemma.ps1 -Prompt "Summarize in 5 bullets" -Files src/foo.py

.EXAMPLE
    pwsh tools/ask_gemma.ps1 `
        -Prompt "Find any places that swallow exceptions silently. List file:line + the exception type." `
        -Files (Get-ChildItem -Recurse SlicerNodeEditor -Filter *.py).FullName `
        -Model gemma4:31b
#>
param(
    [Parameter(Mandatory=$true)]
    [string]$Prompt,
    [string[]]$Files     = @(),
    [string]$Model       = 'gemma4:latest',
    [int]$MaxTokens      = 4096,
    [int]$NumCtx         = 32768,    # IMPORTANT: Ollama defaults to 2048 — too small
    [bool]$Think         = $false,   # Gemma4 thinking burns tokens before output;
                                     # leave off unless you really want CoT
    [string]$System      = '',
    [string]$Format      = '',
    [double]$Temperature = 0.2,
    [string]$Endpoint    = 'http://localhost:11434/api/generate',
    [int]$TimeoutSec     = 600
)

$ErrorActionPreference = 'Stop'

# Stitch together the prompt with any file payloads
$body = New-Object System.Text.StringBuilder
[void]$body.AppendLine($Prompt)
foreach ($f in $Files) {
    if (-not (Test-Path -LiteralPath $f)) {
        Write-Warning "File not found, skipping: $f"
        continue
    }
    $resolved = (Resolve-Path -LiteralPath $f).Path
    [void]$body.AppendLine("")
    [void]$body.AppendLine("--- FILE: $resolved ---")
    [void]$body.AppendLine((Get-Content -Raw -LiteralPath $resolved))
}

$req = @{
    model   = $Model
    prompt  = $body.ToString()
    stream  = $false
    think   = $Think
    options = @{
        num_ctx      = $NumCtx
        num_predict  = $MaxTokens
        temperature  = $Temperature
    }
}
if ($System)  { $req.system = $System }
if ($Format)  { $req.format = $Format }

$json = $req | ConvertTo-Json -Depth 8

# Write to a temp file as UTF-8 (no BOM) to avoid PowerShell quoting mishaps
$tmp = [System.IO.Path]::GetTempFileName()
$utf8NoBom = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText($tmp, $json, $utf8NoBom)

try {
    $r = Invoke-RestMethod -Method Post -Uri $Endpoint `
            -ContentType 'application/json' -InFile $tmp -TimeoutSec $TimeoutSec
} catch {
    Write-Error "Ollama call failed: $_"
    Remove-Item -LiteralPath $tmp -ErrorAction SilentlyContinue
    exit 1
} finally {
    Remove-Item -LiteralPath $tmp -ErrorAction SilentlyContinue
}

# Print stats to stderr so callers can grep just the response on stdout
$inTok  = $r.prompt_eval_count
$outTok = $r.eval_count
$ms     = [math]::Round(($r.total_duration / 1e6))
Write-Information "[ask_gemma] $Model | in=$inTok out=$outTok tokens | $($ms)ms" -InformationAction Continue

Write-Output $r.response
