from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.core import HomeAssistant

from .const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USE_HTTPS,
    CONF_USERNAME,
    DEFAULT_HOST,
    DEFAULT_USE_HTTPS,
    DEFAULT_USERNAME,
    DOMAIN,
    LOGIN_SUCCESS_STATUS,
    NAME,
    PATH_LOGIN,
    PATH_LOGIN_NONCE,
    PATH_LOGIN_SALT,
)

_LOGGER = logging.getLogger(__name__)

# ── Nokia base64url helpers ────────────────────────────────────────────────────

def _nokia_b64encode(data: bytes) -> str:
    """base64url-encode bytes; replace '=' padding with '.'."""
    b64 = base64.urlsafe_b64encode(data).decode()
    n_pad = len(b64) - len(b64.rstrip("="))
    return b64.rstrip("=") + ("." * n_pad)


def _std_b64decode(s: str) -> bytes:
    """Decode standard base64 or Nokia base64url ('.' as padding) to bytes."""
    s = s.replace(".", "=").replace("-", "+").replace("_", "/")
    missing = len(s) % 4
    if missing:
        s += "=" * (4 - missing)
    return base64.b64decode(s)


def _sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _sha256_b64(value: str, salt: str) -> str:
    return base64.b64encode(hashlib.sha256(f"{value}:{salt}".encode()).digest()).decode()


def _sha256_url(value: str, nonce: str) -> str:
    return _nokia_b64encode(hashlib.sha256(f"{value}:{nonce}".encode()).digest())


def _has_session_cookie(session: aiohttp.ClientSession) -> bool:
    if session.cookie_jar is None:
        return False
    return any(
        cookie.key.lower() == "sid"
        and cookie.value
        and cookie.value.lower() != "deleted"
        for cookie in session.cookie_jar
    )


def _login_body_has_session(body: str) -> bool:
    try:
        data = json.loads(body)
    except ValueError:
        return False
    return data.get("result") == 0 and bool(data.get("sid"))


def _redact_login_body(body: str) -> str:
    try:
        data = json.loads(body)
    except ValueError:
        return body[:120]
    for key in ("sid", "token"):
        if key in data:
            data[key] = "<redacted>"
    return json.dumps(data, separators=(",", ":"))


def _safe_login_payload(payload: dict[str, str]) -> dict[str, Any]:
    return {
        "userhash": payload.get("userhash"),
        "RandomKeyhash": payload.get("RandomKeyhash"),
        "nonce": payload.get("nonce"),
        "response": payload.get("response"),
        "response_len": len(payload.get("response", "")),
        "enckey_len": len(payload.get("enckey", "")),
        "enciv_len": len(payload.get("enciv", "")),
    }


def _request_headers(
    base_url: str,
    *,
    content_type: str | None = "application/x-www-form-urlencoded",
) -> dict[str, str]:
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": f"{base_url}/web_whw/",
    }
    if content_type is not None:
        headers["Content-Type"] = content_type
    return headers


def _build_login_payload(
    username: str,
    password: str,
    nonce_data: dict[str, Any],
    alati: str,
) -> dict[str, str]:
    nonce_b64: str = nonce_data["nonce"]
    random_key: str = str(nonce_data.get("randomKey", ""))
    iterations: int = int(nonce_data.get("iterations", 1))
    nonce_bytes = _std_b64decode(nonce_b64)
    escaped_nonce = _nokia_b64encode(nonce_bytes)
    password_hash = _sha256_hex(alati + password) if iterations >= 1 else alati + password

    for _ in range(1, iterations):
        password_hash = hashlib.sha256(bytes.fromhex(password_hash)).hexdigest()

    user_password_hash = _sha256_b64(username, password_hash.lower())

    return {
        "userhash": _sha256_url(username, nonce_b64),
        "RandomKeyhash": _sha256_url(random_key, nonce_b64),
        "response": _sha256_url(user_password_hash, nonce_b64),
        "nonce": escaped_nonce,
        "enckey": _nokia_b64encode(os.urandom(16)),
        "enciv": _nokia_b64encode(os.urandom(16)),
    }


STEP_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
        vol.Required(CONF_USERNAME, default=DEFAULT_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_USE_HTTPS, default=DEFAULT_USE_HTTPS): bool,
    }
)


async def _test_login(hass: HomeAssistant, data: dict[str, Any]) -> str | None:
    """Return None on success or an error key string."""
    host = data[CONF_HOST]
    _LOGGER.debug("nokia_fastmile config: Testing login to %s", host)
    use_https = data.get(CONF_USE_HTTPS, DEFAULT_USE_HTTPS)
    scheme = "https" if use_https else "http"
    base_url = f"{scheme}://{host}"
    username = data[CONF_USERNAME]
    password = data[CONF_PASSWORD]

    connector = aiohttp.TCPConnector(ssl=False)
    try:
        async with aiohttp.ClientSession(
            connector=connector,
            cookie_jar=aiohttp.CookieJar(unsafe=True),
            timeout=aiohttp.ClientTimeout(connect=8, sock_read=12),
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/152.0.0.0 Safari/537.36"
                ),
            },
        ) as session:
            for mode, dotted_nonce in (("form", True),):
                session.cookie_jar.clear()
                async with session.get(
                    base_url + PATH_LOGIN_NONCE,
                    headers=_request_headers(base_url),
                ) as r:
                    if r.status >= 400:
                        _LOGGER.error("nokia_fastmile config: Failed to get nonce HTTP %s", r.status)
                        return "cannot_connect"
                    nonce_data = await r.json(content_type=None) or {}

                salt_userhash = _sha256_url(username, nonce_data["nonce"])
                salt_nonce = _nokia_b64encode(_std_b64decode(nonce_data["nonce"]))
                _LOGGER.debug(
                    "nokia_fastmile config: salt request userhash=%s nonce=%s username=%s randomKey=%s iterations=%s",
                    salt_userhash,
                    salt_nonce,
                    username,
                    nonce_data.get("randomKey"),
                    nonce_data.get("iterations"),
                )

                async with session.get(
                    (
                        base_url
                        + PATH_LOGIN_SALT
                        + f"&userhash={salt_userhash}"
                        + f"&nonce={salt_nonce}"
                    ),
                    headers=_request_headers(base_url),
                ) as r:
                    if r.status >= 400:
                        _LOGGER.error("nokia_fastmile config: Failed to get salt HTTP %s", r.status)
                        return "cannot_connect"
                    salt_data = await r.json(content_type=None) or {}
                    _LOGGER.debug(
                        "nokia_fastmile config: salt fetch completed status=%s keys=%s alati_len=%s",
                        r.status,
                        list(salt_data),
                        len(str(salt_data.get("alati", ""))),
                    )

                payload = _build_login_payload(
                    username,
                    password,
                    nonce_data,
                    str(salt_data.get("alati", "")),
                )
                safe_payload = _safe_login_payload(payload)
                _LOGGER.debug("nokia_fastmile config: login payload safe=%s", safe_payload)
                if mode == "json":
                    post_kwargs = {
                        "json": payload,
                        "headers": _request_headers(base_url, content_type=None),
                    }
                else:
                    post_kwargs = {
                        "data": payload,
                        "headers": _request_headers(base_url),
                    }

                async with session.post(base_url + PATH_LOGIN, **post_kwargs) as r:
                    body = await r.text()
                    cookie_names = [c.key for c in session.cookie_jar] if session.cookie_jar else []
                    _LOGGER.debug(
                        "nokia_fastmile config: login attempt mode=%s nonce=%s status=%s cookies=%s body=%.120s",
                        mode,
                        "dotted" if dotted_nonce else "raw",
                        r.status,
                        cookie_names,
                        _redact_login_body(body),
                    )
                    if r.status in LOGIN_SUCCESS_STATUS and (
                        _login_body_has_session(body) or _has_session_cookie(session)
                    ):
                        _LOGGER.info(
                            "nokia_fastmile config: Login successful with %s payload, %s nonce",
                            mode,
                            "dotted" if dotted_nonce else "raw",
                        )
                        return None
                    _LOGGER.warning(
                        "nokia_fastmile config: login rejected status=%s body=%s payload_safe=%s",
                        r.status,
                        _redact_login_body(body),
                        safe_payload,
                    )

            return "cannot_connect"
            # Step 1 — nonce + crypto params
            async with session.get(base_url + PATH_LOGIN_NONCE) as r:
                if r.status >= 400:
                    _LOGGER.error("nokia_fastmile config: Failed to get nonce — HTTP %s", r.status)
                    return "cannot_connect"
                nonce_data = await r.json(content_type=None)
            nonce_b64: str = nonce_data["nonce"]
            random_key: str = str(nonce_data.get("randomKey", ""))
            iterations: int = int(nonce_data.get("iterations", 1))
            nonce_bytes = _std_b64decode(nonce_b64)

            # Step 2 — salt (empty on this firmware; fetch to maintain correct session state)
            async with session.get(base_url + PATH_LOGIN_SALT) as r:
                if r.status >= 400:
                    _LOGGER.error("nokia_fastmile config: Failed to get salt — HTTP %s", r.status)
                    return "cannot_connect"

            # Step 3 — compute PBKDF2-HMAC-SHA256 hashes and POST
            payload = {
                "userhash":      _nokia_b64encode(
                    hashlib.pbkdf2_hmac("sha256", username.encode(), nonce_bytes, iterations)
                ),
                "RandomKeyhash": _nokia_b64encode(
                    hashlib.pbkdf2_hmac("sha256", random_key.encode(), nonce_bytes, iterations)
                ),
                "response":      _nokia_b64encode(
                    hashlib.pbkdf2_hmac("sha256", password.encode(), nonce_bytes, iterations)
                ),
                "nonce":  nonce_b64.replace("=", "."),
                "enckey": _nokia_b64encode(os.urandom(16)),
                "enciv":  _nokia_b64encode(os.urandom(16)),
            }

            async with session.post(
                base_url + PATH_LOGIN,
                data=payload,
                headers={
                    "Accept": "application/json, text/plain, */*",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            ) as r:
                if r.status in LOGIN_SUCCESS_STATUS and _has_session_cookie(session):
                    _LOGGER.info("nokia_fastmile config: Login successful")
                    return None  # success
                if r.status == 401:
                    _LOGGER.warning("nokia_fastmile config: Invalid auth")
                    return "invalid_auth"
                body = await r.text()
                _LOGGER.error(
                    "nokia_fastmile config: Login failed — HTTP %s body=%.300s",
                    r.status,
                    body,
                )
                return "cannot_connect"

    except aiohttp.ClientConnectorError as err:
        _LOGGER.error("nokia_fastmile config: Connection error — %s", err)
        return "cannot_connect"
    except aiohttp.ServerTimeoutError as err:
        _LOGGER.error("nokia_fastmile config: Timeout error — %s", err)
        return "cannot_connect"
    except Exception as err:  # noqa: BLE001
        _LOGGER.error("nokia_fastmile config: Unexpected error — %s", err)
        return "unknown"
    return None


class NokiaFastMileConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for Nokia FastMile 5G integration."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_HOST])
            self._abort_if_unique_id_configured()

            error = await _test_login(self.hass, user_input)
            if error:
                errors["base"] = error
            else:
                return self.async_create_entry(title=f"{NAME} ({user_input[CONF_HOST]})", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_SCHEMA,
            errors=errors,
        )
