from __future__ import annotations

import logging
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
    NAME,
    PATH_LOGIN,
)

_LOGGER = logging.getLogger(__name__)

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
    use_https = data.get(CONF_USE_HTTPS, DEFAULT_USE_HTTPS)
    scheme = "https" if use_https else "http"
    url = f"{scheme}://{host}{PATH_LOGIN}"
    payload = {
        "username": data[CONF_USERNAME],
        "password": data[CONF_PASSWORD],
    }
    connector = aiohttp.TCPConnector(ssl=False)
    try:
        async with aiohttp.ClientSession(
            connector=connector,
            timeout=aiohttp.ClientTimeout(connect=8, sock_read=12),
        ) as session:
            async with session.post(url, json=payload) as resp:
                if resp.status == 401:
                    return "invalid_auth"
                if resp.status >= 400:
                    return "cannot_connect"
                body = await resp.json(content_type=None)
                if body is None:
                    return "cannot_connect"
    except aiohttp.ClientConnectorError:
        return "cannot_connect"
    except aiohttp.ServerTimeoutError:
        return "cannot_connect"
    except Exception:  # noqa: BLE001
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
