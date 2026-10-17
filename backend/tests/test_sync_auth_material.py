import importlib.util
import json
from pathlib import Path
from urllib.parse import urlencode

import pytest

from app.services.question_sync.auth_material import load_material
from app.services.question_sync.upstream import encode_token


def test_imports_authorized_signed_request_and_har_without_losing_the_seed():
    signed = encode_token("test-session-value")
    url = "https://api.ixunke.cn/xizongcangqiong/api/question?" + urlencode(dict(id=123, token=signed))
    assert load_material(signed) == "test-session-value"
    assert load_material(url) == "test-session-value"
    har = dict(log=dict(entries=[dict(request=dict(url="https://unrelated.example/?token=irrelevant")), dict(request=dict(url=url))]))
    assert load_material(json.dumps(har)) == "test-session-value"
    assert load_material('{"data":{"token":"test-session-value"}}') == "test-session-value"


def test_rejects_other_sites_and_configuration_injection():
    with pytest.raises(ValueError):
        load_material("https://unrelated.example/?token=anything")
    with pytest.raises(ValueError):
        load_material("abc\nMEDKB_DATABASE_URL=other")
    with pytest.raises(ValueError):
        load_material('{"log":{"entries":[]}}')


@pytest.mark.asyncio
async def test_credential_install_requires_upstream_validation_and_preserves_other_settings(tmp_path):
    spec = importlib.util.spec_from_file_location("configure_upstream", Path(__file__).resolve().parents[1] / "scripts/configure_upstream.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source, env = tmp_path / "login.txt", tmp_path / ".env"
    source.write_text("test-session-value", encoding="utf-8")
    env.write_text("MEDKB_DATABASE_URL=existing\nMEDKB_WCYK_TOKEN=old\n", encoding="utf-8")
    class Client:
        fail = True
        def __init__(self, token):
            assert token == "test-session-value"
        async def request(self, *args):
            if self.fail:
                raise ValueError("unauthorized")
            return {"errno": 0, "data": {"id": 123}}
        async def close(self):
            pass
    with pytest.raises(ValueError):
        await module.configure(source, env, factory=Client)
    assert "MEDKB_WCYK_TOKEN=old" in env.read_text()
    Client.fail = False
    assert (await module.configure(source, env, factory=Client))["authenticated"]
    assert env.read_text() == "MEDKB_DATABASE_URL=existing\nMEDKB_WCYK_TOKEN=test-session-value\n"
