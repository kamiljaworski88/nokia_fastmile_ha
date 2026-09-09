from __future__ import annotations

import base64
import hashlib
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
            cookie_jar=aiohttp.CookieJar(),
            timeout=aiohttp.ClientTimeout(connect=8, sock_read=12),
        ) as session:
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

            async with session.post(base_url + PATH_LOGIN, json=payload) as r:
                if r.status in LOGIN_SUCCESS_STATUS:
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
