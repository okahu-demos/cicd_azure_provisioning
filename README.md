# cicd_azure_provisioning

Demo of Azure provisioning pipeline with Monocle zero-code instrumentation and Okahu SRE agent integration.

## How It Works

`deploy_app.py` runs a 4-step Azure provisioning pipeline (Blob, SQL, Kusto, User Accounts). Monocle instruments each step via `okahu.yaml` config — no code changes to the app.

When a step fails, the GitHub Actions workflow:
1. Creates an issue with the error output
2. Comments `@kahu investigate` so the Okahu SRE agent analyzes the trace and posts root cause

## Zero-Code Instrumentation

Uses `python -m monocle_apptrace --config` — a new feature on the [`hoc/claude-skill`](https://github.com/hocokahu/monocle/tree/hoc/claude-skill) branch.

### Usage

```bash
# Basic — instruments deploy_app.py using okahu.yaml config
python -m monocle_apptrace --config okahu.yaml deploy_app.py

# Without --config — default framework instrumentation only (langchain, openai, etc.)
python -m monocle_apptrace deploy_app.py
```

### okahu.yaml Format

```yaml
workflow_name: cicd_test

instrument:
  - package: deploy_app
    method: deploy_azure_blob
    span_name: azure_blob.deploy

  - package: deploy_app
    class: KustoDeploy
    method: deploy_tables
    span_name: kusto.deploy_tables
    inputs:
      include: [cluster_name, database_name, tables]
    output:
      extract: [return_value]
```

Each entry creates a `WrapperMethod` that captures function inputs/outputs as span events (`data.input`, `data.output`).

### What Changed in monocle_apptrace

**File**: `apptrace/src/monocle_apptrace/__main__.py`

The original was an 18-line wrapper that derived `workflow_name` from the filename and called `setup_monocle_telemetry()` with no custom methods. The new version (241 lines) adds:

| Feature | What it does |
|---------|-------------|
| `--config FILE` | Parses `okahu.yaml` to build `WrapperMethod` entries with input/output processors |
| Input/output capture | `_build_input_output_processor()` — captures function args and return values as span events |
| Package pre-import | Imports target packages *after* `setup_monocle_telemetry` so wrapt post-import hooks fire |
| Patched module execution | When the target module was already imported (and patched by wrapt), calls `target_module.main()` instead of `runpy.run_path` which bypasses patches |
| CI scope injection | `_set_ci_scopes()` — detects `GITHUB_RUN_ID`, `GITHUB_SHA`, `GITHUB_WORKFLOW` and registers them as monocle scopes so Okahu indexes them as searchable facts |
| Span flush on exit | Flushes `TracerProvider` (not the empty `MonocleSynchronousMultiSpanProcessor`) before process exit |
| Backwards compatible | Without `--config`, behaves identically to the original |

### Bug Fixes (discovered during development)

| Fix | File | Description |
|-----|------|-------------|
| Span flush no-op | `__main__.py` | `get_monocle_span_processor().force_flush()` was flushing the empty `MonocleSynchronousMultiSpanProcessor`. `BatchSpanProcessor`s are added to the `TracerProvider`, not to it. Fixed to flush the `TracerProvider` directly. |
| kwarg typo | `instrumentor.py` | `trace_provider=` vs `tracer_provider=` nullified the global tracer provider after setup |

### Key Discovery: Scopes vs Span Attributes

Okahu indexes `scope.*` span attributes as searchable facts. Plain span attributes (like `github.run_id`) are NOT searchable via the fact API. The `_set_ci_scopes()` function uses monocle's `set_scopes()` → OTel baggage → `scope.git.run.id` attribute, which Okahu indexes and the SRE agent can query by.

## Environment Setup

```bash
cp .env.example .env
# Edit .env with your OKAHU_API_KEY
```

| Variable | Description |
|----------|-------------|
| `OKAHU_API_KEY` | Okahu API key for trace export |
| `OKAHU_INGESTION_ENDPOINT` | Okahu ingestion endpoint |
| `MONOCLE_EXPORTER` | Comma-separated exporters: `file`, `okahu`, `console` |

## Running Locally

```bash
pip install "monocle_apptrace @ git+https://github.com/hocokahu/monocle.git@hoc/claude-skill#subdirectory=apptrace" pyyaml
source .env
MONOCLE_EXPORTER=file python -m monocle_apptrace --config okahu.yaml deploy_app.py
```

Traces are written to `.monocle/` directory.

## CI/CD (GitHub Actions)

The workflow at `.github/workflows/cicd-deploy-example.yml`:
1. Installs `monocle_apptrace` from the fork branch
2. Loads `.env` and sets exporters (always `file`, adds `okahu` if `OKAHU_API_KEY` is set)
3. Runs `python -m monocle_apptrace --config okahu.yaml deploy_app.py`
4. On failure: creates GitHub issue and triggers `@kahu` SRE agent
5. Uploads traces as build artifacts
