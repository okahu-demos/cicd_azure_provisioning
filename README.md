# cicd_azure_provisioning

Demo of Azure provisioning pipeline with Monocle zero-code instrumentation and Okahu SRE agent integration.

## How It Works

`deploy_app.py` runs a 4-step Azure provisioning pipeline (Blob, SQL, Kusto, User Accounts). Monocle instruments each step via `okahu.yaml` config — no code changes to the app.

When a step fails, the GitHub Actions workflow:
1. Creates an issue with the error output
2. Comments `@kahu investigate` so the Okahu SRE agent analyzes the trace and posts root cause

### Zero-Code Instrumentation

Monocle automatically discovers the config at `.monocle/okahu.yaml` — no `--config` flag needed.

#### Usage

```bash
# Instruments deploy_app.py using .monocle/okahu.yaml config
python -m monocle_apptrace deploy_app.py
```

#### .monocle/okahu.yaml Format

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

## Prerequisites

- Python 3.9+
- A GitHub account (for CI/CD workflows)
- An [Okahu](https://portal.okahu.co) account (for trace export and SRE agent)

## Get Started

### Clone and Install

```bash
git clone https://github.com/okahu-demos/cicd_azure_provisioning.git
cd cicd_azure_provisioning
uv tool install monocle_apptrace==0.8.1a4 --index-url https://okahu.jfrog.io/artifactory/api/pypi/okahu-patch-pypi/simple
```

### Environment Setup

```bash
cp .env.example .env
# Edit .env with your keys
```

| Variable | Description |
|----------|-------------|
| `OKAHU_API_KEY` | Okahu API key for trace export |
| `OKAHU_INGESTION_ENDPOINT` | Okahu ingestion endpoint |
| `MONOCLE_EXPORTER` | Comma-separated exporters: `file`, `okahu`, `console` |

#### Connect to Okahu Account

Sign up or log in at [portal.okahu.co](https://portal.okahu.co) to get your `OKAHU_API_KEY` and `OKAHU_INGESTION_ENDPOINT`.

### Running Locally

```bash
source .env
MONOCLE_EXPORTER=file python -m monocle_apptrace deploy_app.py
```

Traces are written to `.monocle/` directory.

## CI/CD (GitHub Actions)

Go to the **Actions** tab and click **Run workflow** to trigger a run.

The workflow at `.github/workflows/cicd-deploy-summary-only-example.yml`:
1. Installs `monocle_apptrace` and runs the deployment pipeline with zero-code instrumentation
2. On failure: fetches trace IDs from Okahu for the current run
3. On failure: calls the Kahu SRE Agent with trace context for root cause analysis
4. On failure: creates a GitHub Issue with the Kahu analysis
5. Uploads deployment logs and traces as build artifacts
