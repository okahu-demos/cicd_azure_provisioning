"""Monocle tracing wrapper: setup must happen before importing deploy_app
so wrap_function_wrapper patches the classes before main() uses them."""
import os
import sys
from monocle_apptrace.instrumentation.common.instrumentor import setup_monocle_telemetry
from monocle_apptrace.instrumentation.common.utils import set_scopes

workflow_name = os.getenv("MONOCLE_WORKFLOW_NAME", "cicd_azure_provisioning")
setup_monocle_telemetry(workflow_name=workflow_name)

run_id = os.getenv("GITHUB_RUN_ID")
if run_id:
    set_scopes({"git.run.id": f"github_{run_id}"})

import deploy_app

try:
    deploy_app.main()
except SystemExit as e:
    code = e.code if e.code is not None else 0
except Exception as e:
    print(e)
    code = 1
else:
    code = 0
finally:
    from opentelemetry.trace import get_tracer_provider
    get_tracer_provider().force_flush(timeout_millis=10000)

sys.exit(code)
