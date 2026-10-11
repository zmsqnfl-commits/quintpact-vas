"""Real HTTP error contracts use isolated synthetic state, never user memory."""
import http.client
import json
import os
import shutil
import socket
import urllib.parse

import pytest

from test_memory_policy import event, launched, memory_files, seed

pytestmark = pytest.mark.skipif(
    os.name != "nt" or not shutil.which("powershell.exe"),
    reason="Windows PowerShell required",
)
MAX_BODY = 5 * 1024 * 1024


@pytest.fixture(scope="module")
def runtime(tmp_path_factory):
    with launched(tmp_path_factory.mktemp("http-errors")) as instance:
        yield instance


def raw_request(client, path, body=b"", *, chunked=False, auth=True, length=None):
    """Allow chunked input and oversized headers without uploading a giant body."""
    address = urllib.parse.urlsplit(client.base)
    connection = http.client.HTTPConnection(address.hostname, address.port, timeout=10)
    headers = {"Content-Type": "application/json", "Connection": "close"}
    if auth:
        headers.update({"X-VAS-Token": client.token, "Origin": client.base})
    try:
        if length is not None:
            connection.putrequest("POST", path)
            for name, value in headers.items():
                connection.putheader(name, value)
            connection.putheader("Content-Length", str(length))
            connection.endheaders()
        elif chunked:
            chunks = (body[start:start + 32768] for start in range(0, len(body), 32768))
            connection.request("POST", path, chunks, headers, encode_chunked=True)
        else:
            connection.request("POST", path, body, headers)
        response = connection.getresponse()
        return response.status, json.loads(response.read())
    finally:
        connection.close()


def assert_unchanged_and_alive(client, state, before):
    assert memory_files(state) == before
    assert client.request("/api/heartbeat", "POST", {})[0] == 200
    assert memory_files(state) == before


@pytest.mark.parametrize("mode", [None, True, 1, "", "invalid", "Merge", [], {}, ["merge"]])
def test_invalid_import_mode_is_400_and_preserves_state(runtime, mode):
    client, state = runtime
    seed(state, [event()])
    before = memory_files(state)
    body = json.dumps({"mode": mode, "data": {"events": [event(1)]}}).encode()
    status, result = raw_request(client, "/api/memory/import", body)
    assert (status, result["code"]) == (400, "invalid_memory_mode")
    assert_unchanged_and_alive(client, state, before)


@pytest.mark.parametrize("mode,expected", [(None, 2), ("merge", 2), ("replace", 1)])
def test_import_default_and_valid_modes_still_work(runtime, mode, expected):
    client, state = runtime
    seed(state, [event()])
    body = {"data": {"events": [event(1)]}}
    if mode is not None:
        body["mode"] = mode
    assert client.request("/api/memory/import", "POST", body)[0] == 200
    assert client.request("/api/memory/status")[1]["count"] == expected


@pytest.mark.parametrize("body", [b'{"mode":', b'{"consent":tru}', b'{]'])
def test_malformed_json_is_400_before_mutation(runtime, body):
    client, state = runtime
    seed(state, [event()])
    before = memory_files(state)
    status, result = raw_request(client, "/api/memory/import", body)
    assert (status, result["code"]) == (400, "invalid_json")
    assert_unchanged_and_alive(client, state, before)


def test_oversized_content_length_is_413_before_reading_or_mutation(runtime):
    client, state = runtime
    seed(state, [event()])
    before = memory_files(state)
    status, result = raw_request(client, "/api/memory/import", length=MAX_BODY + 1)
    assert (status, result["code"]) == (413, "request_body_too_large")
    assert_unchanged_and_alive(client, state, before)


def test_oversized_chunked_body_is_413_without_mutation(runtime):
    client, state = runtime
    seed(state, [event()])
    before = memory_files(state)
    body = b"{}" + b" " * (MAX_BODY - 1)
    status, result = raw_request(client, "/api/memory/import", body, chunked=True)
    assert (status, result["code"]) == (413, "request_body_too_large")
    assert_unchanged_and_alive(client, state, before)


@pytest.mark.parametrize("chunked", [False, True], ids=["content-length", "chunked"])
@pytest.mark.parametrize("size", [MAX_BODY - 1, MAX_BODY], ids=["below-limit", "at-limit"])
def test_valid_body_at_inclusive_byte_boundary_is_accepted(runtime, chunked, size):
    client, state = runtime
    seed(state, [event()])
    before = memory_files(state)
    body = b"{}" + b" " * (size - 2)
    status, result = raw_request(client, "/api/heartbeat", body, chunked=chunked)
    assert status == 200 and result["ok"] is True
    assert_unchanged_and_alive(client, state, before)


def test_oversized_unauthenticated_request_is_still_401(runtime):
    client, state = runtime
    seed(state, [event()])
    before = memory_files(state)
    status, _ = raw_request(client, "/api/memory/import", auth=False, length=MAX_BODY + 1)
    assert status == 401
    assert_unchanged_and_alive(client, state, before)


def test_chat_keeps_its_separate_64_kib_limit(runtime):
    client, state = runtime
    seed(state, [event()])
    before = memory_files(state)
    status, result = raw_request(client, "/api/chat/session/design", length=65537)
    assert (status, result["code"]) == (413, "session_input_too_large")
    assert_unchanged_and_alive(client, state, before)


def test_disconnected_client_does_not_stop_the_request_loop(runtime):
    client, state = runtime
    seed(state, [event()])
    before = memory_files(state)
    address = urllib.parse.urlsplit(client.base)
    with socket.create_connection((address.hostname, address.port), timeout=5) as connection:
        request = (
            f"POST /api/memory/import HTTP/1.1\r\nHost: {address.netloc}\r\n"
            f"X-VAS-Token: {client.token}\r\nOrigin: {client.base}\r\n"
            "Content-Type: application/json\r\nContent-Length: 1\r\nConnection: close\r\n\r\n{"
        )
        connection.sendall(request.encode())
    assert_unchanged_and_alive(client, state, before)


def test_internal_storage_error_remains_500_and_server_recovers(tmp_path):
    with launched(tmp_path / "internal-error") as (client, state):
        # A synthetic directory at the consent file path forces a filesystem error.
        control = state / "memory-consent.json"
        control.mkdir()
        before = memory_files(state)
        status, result = raw_request(client, "/api/memory/consent", b'{"consent":true}')
        assert (status, result["code"]) == (500, "request_failed")
        assert_unchanged_and_alive(client, state, before)
        control.rmdir()
        assert client.request("/api/memory/consent", "POST", {"consent": True})[0] == 200
