"""Wrapper that sets CI/CD scopes and runs deploy_app.py with Monocle tracing."""
import os
import sys
import runpy
from monocle_apptrace.instrumentation.common.instrumentor import setup_monocle_telemetry
from monocle_apptrace.instrumentation.common.utils import set_scopes

workflow_name = os.getenv("MONOCLE_WORKFLOW_NAME", "cicd_azure_provisioning")
setup_monocle_telemetry(workflow_name=workflow_name)

run_id = os.getenv("GITHUB_RUN_ID")
if run_id:
    set_scopes({"git.run.id": f"github_{run_id}"})

try:
    runpy.run_path("deploy_app.py", run_name="__main__")
except SystemExit as e:
    code = e.code if e.code is not None else 0
except Exception as e:
    print(e)
    code = 1
else:
    code = 0
finally:
    from opentelemetry.trace import get_tracer_provider
    provider = get_tracer_provider()
    if hasattr(provider, "force_flush"):
        provider.force_flush(timeout_millis=10000)

sys.exit(code)
