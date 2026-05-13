"""Tests for ``FMGClient`` JSON-RPC transport.

We mock the underlying HTTP layer with ``respx`` to verify:
- Status code mapping → typed exceptions.
- Retry on transient HTTP / network errors.
- CRUD verbs send the right JSON-RPC method.
- ``multiplex`` uses ``set`` with multiple params.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from fmg_api_client import (
    AuthError,
    DuplicateError,
    FMGClient,
    FMGError,
    NotFoundError,
    SessionManager,
)


def _ok(data: object) -> dict[str, object]:
    return {
        "id": 1,
        "result": [
            {
                "status": {"code": 0, "message": "OK"},
                "data": data,
                "url": "/anything",
            }
        ],
    }


def _err(code: int, message: str) -> dict[str, object]:
    return {
        "id": 1,
        "result": [
            {
                "status": {"code": code, "message": message},
                "data": None,
                "url": "/anything",
            }
        ],
    }


def _build_client(*, max_retries: int = 1) -> FMGClient:
    sm = SessionManager(host="fmg.test", api_token="t0k3n", verify_ssl=False)
    client = FMGClient(sm, max_retries=max_retries)
    # Inject a real httpx.AsyncClient so respx can intercept.
    client._http = httpx.AsyncClient(
        verify=False,
        headers=sm.auth_headers(),
        timeout=httpx.Timeout(connect=1.0, read=1.0, write=1.0, pool=1.0),
    )
    return client


@pytest.mark.asyncio
async def test_get_returns_data_on_ok() -> None:
    async with respx.mock(base_url="https://fmg.test") as router:
        router.post("/jsonrpc").mock(
            return_value=httpx.Response(200, json=_ok({"hello": "world"}))
        )
        c = _build_client()
        try:
            data = await c.get("/sys/status")
        finally:
            await c._http.aclose()
        assert data == {"hello": "world"}


@pytest.mark.asyncio
async def test_set_returns_data_on_ok() -> None:
    async with respx.mock(base_url="https://fmg.test") as router:
        router.post("/jsonrpc").mock(return_value=httpx.Response(200, json=_ok({"oid": 6116})))
        c = _build_client()
        try:
            data = await c.set("/some/url", {"a": 1})
        finally:
            await c._http.aclose()
        assert data == {"oid": 6116}


@pytest.mark.asyncio
async def test_not_found_raises_typed_exception() -> None:
    async with respx.mock(base_url="https://fmg.test") as router:
        router.post("/jsonrpc").mock(
            return_value=httpx.Response(200, json=_err(-3, "Object does not exist"))
        )
        c = _build_client()
        try:
            with pytest.raises(NotFoundError) as ei:
                await c.get("/missing")
        finally:
            await c._http.aclose()
        assert ei.value.status_code == -3


@pytest.mark.asyncio
async def test_duplicate_raises_typed_exception() -> None:
    async with respx.mock(base_url="https://fmg.test") as router:
        router.post("/jsonrpc").mock(
            return_value=httpx.Response(200, json=_err(-6, "Already exists"))
        )
        c = _build_client()
        try:
            with pytest.raises(DuplicateError):
                await c.add("/dup/url", {})
        finally:
            await c._http.aclose()


@pytest.mark.asyncio
async def test_no_permission_raises_auth_error() -> None:
    async with respx.mock(base_url="https://fmg.test") as router:
        router.post("/jsonrpc").mock(
            return_value=httpx.Response(200, json=_err(-11, "No permission"))
        )
        c = _build_client()
        try:
            with pytest.raises(AuthError):
                await c.get("/restricted")
        finally:
            await c._http.aclose()


@pytest.mark.asyncio
async def test_unknown_code_raises_generic_fmg_error() -> None:
    async with respx.mock(base_url="https://fmg.test") as router:
        router.post("/jsonrpc").mock(
            return_value=httpx.Response(
                200, json=_err(-10, "The data is invalid for selected url")
            )
        )
        c = _build_client()
        try:
            with pytest.raises(FMGError) as ei:
                await c.set("/bad/payload", {})
        finally:
            await c._http.aclose()
        assert ei.value.status_code == -10
        assert not isinstance(ei.value, NotFoundError)
        assert not isinstance(ei.value, DuplicateError)


@pytest.mark.asyncio
async def test_retries_on_transient_503_then_succeeds() -> None:
    async with respx.mock(base_url="https://fmg.test") as router:
        route = router.post("/jsonrpc").mock(
            side_effect=[
                httpx.Response(503),
                httpx.Response(200, json=_ok("recovered")),
            ]
        )
        c = _build_client(max_retries=3)
        try:
            data = await c.get("/sys/status")
        finally:
            await c._http.aclose()
        assert data == "recovered"
        assert route.call_count == 2


@pytest.mark.asyncio
async def test_multiplex_sends_set_with_all_params() -> None:
    async with respx.mock(base_url="https://fmg.test") as router:
        route = router.post("/jsonrpc").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": 1,
                    "result": [
                        {
                            "status": {"code": 0, "message": "OK"},
                            "data": "a",
                        },
                        {
                            "status": {"code": 0, "message": "OK"},
                            "data": "b",
                        },
                    ],
                },
            )
        )
        c = _build_client()
        try:
            data = await c.multiplex([{"url": "/x", "data": {"a": 1}}, {"url": "/y", "data": {}}])
        finally:
            await c._http.aclose()
        assert data == ["a", "b"]
        # Verify the JSON-RPC method is "set" with both params in one call.
        sent_payload = route.calls[0].request.read()
        import json

        body = json.loads(sent_payload)
        assert body["method"] == "set"
        assert len(body["params"]) == 2


@pytest.mark.asyncio
async def test_multiplex_empty_returns_empty() -> None:
    c = _build_client()
    try:
        data = await c.multiplex([])
    finally:
        await c._http.aclose()
    assert data == []


@pytest.mark.asyncio
async def test_call_before_connect_raises() -> None:
    sm = SessionManager(host="fmg.test", api_token="t", verify_ssl=False)
    c = FMGClient(sm)
    with pytest.raises(FMGError, match="Client not connected"):
        await c.get("/sys/status")
