# Tools

Local-LLM helpers for offloading token-heavy code analysis to Gemma running
in Ollama on this machine, so Claude doesn't have to read entire files into
its context.

## Setup

- Ollama running at `http://localhost:11434`
- A Gemma model pulled (`gemma4:latest` for fast 8B, `gemma4:31b` for harder
  reasoning at the cost of throughput).

## ask_gemma.ps1

Single-shot wrapper around Ollama's `/api/generate`. Reads files locally and
includes them in the prompt; only the model's response goes to stdout (and
into Claude's context).

```powershell
# Set per-process for the session:
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force

# Quick text completion
pwsh tools/ask_gemma.ps1 -Prompt 'Reply with PONG' -Model gemma4:latest

# Summarize a single file
pwsh tools/ask_gemma.ps1 `
    -Prompt 'Summarize this in 5 bullets.' `
    -Files SlicerNodeEditor/NodeGraph/scene.py

# Audit many files in one call (works best on the 31B model)
pwsh tools/ask_gemma.ps1 `
    -Prompt 'List places where input is not validated.' `
    -Files (Get-ChildItem -Recurse SlicerNodeEditor -Filter *.py).FullName `
    -Model gemma4:31b -NumCtx 65536
```

### Important parameters

| Param         | Why it matters                                                         |
|---------------|-------------------------------------------------------------------------|
| `-NumCtx`     | Ollama defaults to **2048 tokens** regardless of model. For real files, set this to 16384 / 32768 / 65536 explicitly or your prompt gets silently truncated. |
| `-Think`      | Gemma 4 has thinking mode ON by default and will spend `num_predict` on internal reasoning that doesn't surface as `.response`. Default is `$false` here for that reason. |
| `-MaxTokens`  | `num_predict` — cap on response length.                                 |
| `-Model`      | `gemma4:latest` (8B) for speed, `gemma4:31b` for harder reasoning.      |

## gemma_audit_per_file.ps1

Iterates a glob, asks the SAME prompt of each file, aggregates findings.
Pattern of choice when one big call would degenerate into repetition (8B
gets confused on >5K input tokens).

```powershell
pwsh tools/gemma_audit_per_file.ps1 `
    -Glob 'SlicerNodeEditor\NodeGraph\*.py' `
    -Root 'D:\Projects\1004_Nodes_For_3D_Slicer' `
    -Prompt 'List every place that catches Exception without re-raising. Output: line N - <action>. If none: NONE'
```

## Caveats / lessons learned

- **8B hallucinates line numbers.** Use Gemma to *find candidates*, then grep
  to verify.
- **`num_ctx`** defaults too low. Override it.
- **Think mode** silently eats your output budget unless `think: false`.
- **Big single prompts (>5K tokens) on the 8B** start to repeat themselves.
  Chunk per-file with `gemma_audit_per_file.ps1` instead.
- **31B is slow** on most consumer hardware — fine for a few well-chosen
  prompts, not for batch loops.
