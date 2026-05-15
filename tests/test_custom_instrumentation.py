"""Verify custom instrumentation produces spans in monocle_apptrace 0.8.1a4."""
import os
import sys
import json

os.environ["MONOCLE_EXPORTERS"] = "memory"

import pytest
from monocle_apptrace.instrumentation.common.instrumentor import (
    setup_monocle_telemetry,
    load_custom_instrumentation,
    get_monocle_span_processor,
)


@pytest.fixture(autouse=True)
def _setup_telemetry():
    instrumentor = setup_monocle_telemetry(
        workflow_name="test_cicd_custom",
        monocle_exporters_list="memory",
    )
    yield instrumentor
    from opentelemetry.trace import get_tracer_provider
    provider = get_tracer_provider()
    provider.force_flush(timeout_millis=5000)


def _get_exported_spans():
    from opentelemetry.trace import get_tracer_provider
    get_tracer_provider().force_flush(timeout_millis=5000)
    processor = get_monocle_span_processor()
    for sp in processor._span_processors:
        if hasattr(sp, "span_exporter") and hasattr(sp.span_exporter, "get_finished_spans"):
            return list(sp.span_exporter.get_finished_spans())
    return []


class TestCustomInstrumentationYAML:
    def test_yaml_loads_four_methods(self):
        methods = load_custom_instrumentation()
        assert len(methods) == 4
        names = {m.to_dict()["span_name"] for m in methods}
        assert names == {
            "azure_blob.deploy",
            "azure_sql.deploy",
            "kusto.deploy_tables",
            "user_account.provision",
        }

    def test_all_methods_have_custom_output_processor(self):
        for m in load_custom_instrumentation():
            d = m.to_dict()
            assert d["output_processor"] is not None
            assert d["output_processor"]["type"] == "custom"


class TestSpanGeneration:
    def test_blob_deploy_produces_spans(self):
        import deploy_app
        blob = deploy_app.AzureBlobDeploy()
        blob.deploy("acct", "rg", "eastus")
        spans = _get_exported_spans()
        custom_spans = [s for s in spans if s.name == "azure_blob.deploy"]
        assert len(custom_spans) >= 1
        span = custom_spans[0]
        assert span.attributes.get("span.type") == "custom"
        event_names = [e.name for e in span.events]
        assert "data.input" in event_names
        assert "data.output" in event_names

    def test_sql_deploy_produces_spans(self):
        import deploy_app
        sql = deploy_app.AzureSQLDeploy()
        sql.deploy("srv", "db", "rg")
        spans = _get_exported_spans()
        custom_spans = [s for s in spans if s.name == "azure_sql.deploy"]
        assert len(custom_spans) >= 1

    def test_kusto_deploy_produces_spans(self):
        import deploy_app
        kusto = deploy_app.KustoDeploy()
        kusto.deploy_tables("cluster", "db", ["t1"])
        spans = _get_exported_spans()
        custom_spans = [s for s in spans if s.name == "kusto.deploy_tables"]
        assert len(custom_spans) >= 1

    def test_user_provision_error_produces_span_with_error(self):
        import deploy_app
        prov = deploy_app.UserAccountProvision()
        with pytest.raises(RuntimeError):
            prov.create_accounts("user", "user@example.com", "Admin")
        spans = _get_exported_spans()
        custom_spans = [s for s in spans if s.name == "user_account.provision"]
        assert len(custom_spans) >= 1
        span = custom_spans[0]
        assert span.status.status_code.name == "ERROR"

    def test_workflow_span_created_as_parent(self):
        import deploy_app
        blob = deploy_app.AzureBlobDeploy()
        blob.deploy("acct", "rg", "eastus")
        spans = _get_exported_spans()
        workflow_spans = [s for s in spans if s.name == "workflow"]
        assert len(workflow_spans) >= 1
        wf = workflow_spans[-1]
        assert wf.attributes.get("span.type") == "workflow"
        assert wf.attributes.get("entity.1.name") is not None

    def test_span_has_monocle_version(self):
        import deploy_app
        blob = deploy_app.AzureBlobDeploy()
        blob.deploy("acct", "rg", "eastus")
        spans = _get_exported_spans()
        for s in spans:
            assert s.attributes.get("monocle_apptrace.version") == "0.8.1a4"

    def test_input_event_captures_args(self):
        import deploy_app
        blob = deploy_app.AzureBlobDeploy()
        blob.deploy("my_account", "my_rg", "westus2")
        spans = _get_exported_spans()
        custom_spans = [s for s in spans if s.name == "azure_blob.deploy"]
        span = custom_spans[-1]
        input_event = next(e for e in span.events if e.name == "data.input")
        input_data = json.loads(input_event.attributes["input"])
        assert "my_account" in str(input_data)
