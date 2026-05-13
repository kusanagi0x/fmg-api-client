"""Tests for ``SessionManager`` (token vs user/pass auth)."""

from __future__ import annotations

import httpx
import pytest
import respx

from fmg_api_client import AuthError, SessionManager


def test_token_auth_headers() -> None:
    sm = SessionManager(host="fmg.test", api_token="secret-token")
    assert sm.auth_headers() == {"Authorization": "Bearer secret-token"}
    assert sm.is_token_auth is True


def test_no_auth_headers_for_user_pass() -> None:
    sm = SessionManager(host="fmg.test", username="admin", password="x")
    assert sm.auth_headers() == {}
    assert sm.is_token_auth is False


def test_inject_session_token_only_when_user_pass() -> None:
    sm = SessionManager(host="fmg.test", username="admin", password="x")
    sm._session_token = "abc123"
    payload = sm.inject_session({"method": "get"})
    assert payload["session"] == "abc123"


def test_inject_session_skipped_for_token_auth() -> None:
    sm = SessionManager(host="fmg.test", api_token="t")
    sm._session_token = "abc123"
    payload = sm.inject_session({"method": "get"})
    assert "session" not in payload


def test_base_url_uses_https() -> None:
    sm = SessionManager(host="fmg.test")
    assert sm.base_url == "https://fmg.test/jsonrpc"


@pytest.mark.asyncio
async def test_login_skipped_for_token_auth() -> None:
    sm = SessionManager(host="fmg.test", api_token="t")
    async with httpx.AsyncClient() as c:
        await sm.login(c)
    assert sm.session_token is None


@pytest.mark.asyncio
async def test_login_with_credentials_stores_session_token() -> None:
    async with respx.mock(base_url="https://fmg.test") as router:
        router.post("/jsonrpc").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": 1,
                    "session": "session-xyz",
                    "result": [{"status": {"code": 0, "message": "OK"}}],
                },
            )
        )
        sm = SessionManager(host="fmg.test", username="admin", password="p")
        async with httpx.AsyncClient() as c:
            await sm.login(c)
        assert sm.session_token == "session-xyz"


@pytest.mark.asyncio
async def test_login_without_credentials_raises_auth_error() -> None:
    sm = SessionManager(host="fmg.test")
    async with httpx.AsyncClient() as c:
        with pytest.raises(AuthError):
            await sm.login(c)


@pytest.mark.asyncio
async def test_login_with_bad_credentials_raises_auth_error() -> None:
    async with respx.mock(base_url="https://fmg.test") as router:
        router.post("/jsonrpc").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": 1,
                    "result": [
                        {
                            "status": {
                                "code": -22,
                                "message": "Login failed",
                            }
                        }
                    ],
                },
            )
        )
        sm = SessionManager(host="fmg.test", username="admin", password="wrong")
        async with httpx.AsyncClient() as c:
            with pytest.raises(AuthError):
                await sm.login(c)
