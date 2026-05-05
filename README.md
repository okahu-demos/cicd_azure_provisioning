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

### Files Changed in monocle_apptrace

All changes are on the [`hoc/claude-skill`](https://github.com/hocokahu/monocle/tree/hoc/claude-skill) branch of `hocokahu/monocle`.

#### `apptrace/src/monocle_apptrace/__main__.py`

The CLI entry point for `python -m monocle_apptrace`. Key additions:

- **Lines 20–27** `_load_yaml_config()` — loads `okahu.yaml` config file
- **Lines 30–113** `_build_input_output_processor()` — creates output processors that capture function args as `data.input` events and return values as `data.output` events on spans
- **Lines 116–138** `_build_wrapper_methods()` — reads `instrument:` entries from config and builds `WrapperMethod` objects with `task_wrapper`/`atask_wrapper`
- **Lines 141–155** `_set_ci_scopes()` — detects GitHub Actions env vars (`GITHUB_RUN_ID`, `GITHUB_SHA`, `GITHUB_WORKFLOW`) and registers them as monocle scopes via `set_scopes()`. This produces `scope.git.run.id = "github_{run_id}"` on every span, which Okahu indexes as a searchable fact.
- **Lines 165–184** `main()` config handling — parses `--config`, builds wrapper methods, calls `setup_monocle_telemetry()` with `union_with_default_methods=True`
- **Lines 196–197** — captures `TracerProvider` reference via `get_tracer_provider()` for reliable flush
- **Lines 214–216** — flushes `TracerProvider` directly in `finally` block (not the empty `MonocleSynchronousMultiSpanProcessor`)

#### `apptrace/src/monocle_apptrace/instrumentation/common/span_handler.py`

- **Lines 100–102** in `set_default_monocle_attributes()` — reads `GITHUB_RUN_ID` env var and sets `github.run_id` as a span attribute on every span

### Scopes vs Span Attributes

Okahu indexes `scope.*` span attributes as searchable facts. Plain span attributes (like `github.run_id`) are NOT searchable via the fact API. The `_set_ci_scopes()` function uses monocle's `set_scopes()` → OTel baggage → `scope.git.run.id` attribute, which Okahu indexes and the SRE agent queries via `duration_fact=test_runs&fact_ids=github_{run_id}`.

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
