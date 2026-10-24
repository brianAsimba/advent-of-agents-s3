"""Day 19 tests: catalog lifecycle, registry meta-MCP, fail-closed resolution, credential binding, screening."""
import asyncio
import inspect

import pytest
from starlette.testclient import TestClient

import catalog
import platform_tools as pt
import registry_mcp
import release_mcp

SERVICE, BINDING = "release-notes-mcp", "release-notes-api-key"


@pytest.fixture(autouse=True)
def state(tmp_path, monkeypatch):
    monkeypatch.setenv("DAY19_STATE", str(tmp_path))  # for the registry subprocess
    monkeypatch.setattr(catalog, "STATE", tmp_path)
    catalog.bind_credential(BINDING)
    catalog.register_service(SERVICE, "http://127.0.0.1:8191/mcp", "1.3.2", "Product release notes", BINDING)


def test_registry_tools_never_expose_secrets():
    hits = registry_mcp.search_mcp_servers("release")
    assert [h["name"] for h in hits] == [SERVICE] and "auth_binding" not in hits[0]
    assert "auth_binding" not in registry_mcp.get_mcp_server(SERVICE)
    assert registry_mcp.fetch_available_bindings(SERVICE) == [{"binding": BINDING, "type": "api_key"}]
    assert catalog.credential(BINDING) not in repr([hits, registry_mcp.get_mcp_server(SERVICE)])


def test_resolve_through_meta_mcp_follows_endpoint_updates():
    assert asyncio.run(pt.resolve("release"))["url"].endswith(":8191/mcp")
    catalog.update_endpoint(SERVICE, "http://127.0.0.1:8192/mcp", "1.3.3")
    t = asyncio.run(pt.resolve("release"))
    assert t["url"].endswith(":8192/mcp") and t["version"] == "1.3.3" and t["binding"] == BINDING


def test_revoked_or_unknown_fails_closed():
    catalog.revoke(SERVICE)
    with pytest.raises(pt.Unresolvable, match="REVOKED"):
        asyncio.run(pt.resolve("release"))
    with pytest.raises(pt.Unresolvable, match="none"):
        asyncio.run(pt.resolve("payroll"))


def test_header_provider_reads_the_current_credential_after_rotation():
    agent, _ = asyncio.run(pt.governed_agent("release"))
    provider = agent.tools[0].header_provider
    first = provider(object())["Authorization"]
    catalog.bind_credential(BINDING)
    assert provider(object())["Authorization"] != first == f"Bearer {first.split()[1]}"


def test_agent_code_holds_no_url_or_key():
    src = inspect.getsource(pt.governed_agent)
    assert "127.0.0.1" not in src and "RELEASE_API_KEY" not in src and catalog.credential(BINDING) not in src


def test_screening_blocks_injected_tool_results_only():
    tool = type("T", (), {"name": "get_release_notes"})()
    bad = {"notes": release_mcp.RELEASES["1.4.0"]}
    assert pt.screen_result(tool, {}, None, bad) == {"status": "blocked", "message": pt.BLOCKED}
    assert pt.screen_result(tool, {}, None, {"notes": release_mcp.RELEASES["1.3.2"]}) is None


def test_server_rejects_missing_or_stale_key():
    app = release_mcp.require_key(release_mcp.build_server("1.3.2").streamable_http_app())
    body = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
        "protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}}}
    h = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
    with TestClient(app, base_url="http://127.0.0.1:8191") as c:  # the server rejects unknown Host headers
        assert c.post("/mcp", json=body, headers=h).status_code == 401
        old = catalog.credential(BINDING)
        assert c.post("/mcp", json=body, headers={**h, "Authorization": f"Bearer {old}"}).status_code == 200
        catalog.bind_credential(BINDING)  # rotate
        assert c.post("/mcp", json=body, headers={**h, "Authorization": f"Bearer {old}"}).status_code == 401
