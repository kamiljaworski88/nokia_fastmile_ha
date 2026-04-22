"""Data update coordinator for nokia_fastmile.

Nokia FastMile 5G14-B CGI API
— verified via browser DevTools:

Authentication (3 steps):
  1. GET  /login_web_app.cgi?nonce
     → {"nonce": "<b64>", "randomKey": "<n>", "iterations": 1,
        "pubkey": "-----BEGIN PUBLIC KEY-----..."}

  2. GET  /login_web_app.cgi?salt
     → {"alati": ""}  (empty salt on this firmware)

  3. POST /login_web_app.cgi  → HTTP 299 on success
     Body:
       userhash      = nokia_b64(pbkdf2_hmac_sha256(key=username,   salt=nonce_bytes, n=iterations))
       RandomKeyhash = nokia_b64(pbkdf2_hmac_sha256(key=randomKey,  salt=nonce_bytes, n=iterations))
       response      = nokia_b64(pbkdf2_hmac_sha256(key=password,   salt=nonce_bytes, n=iterations))
       nonce         = original nonce string with '=' → '.'
       enckey        = nokia_b64(16 random bytes)
       enciv         = nokia_b64(16 random bytes)

   nokia_b64 = base64url where '=' padding is replaced by '.'

Data endpoints (plain GET, no body):
  /overview_get_web_app.cgi
  /dashboard_device_info_status_web_app.cgi

overview response (confirmed):
  connection_status[0].ConnectionStatus   → 0|1
  WAN[0].Mode                             → "CellularOnly"
  WAN[0].ActiveWAN                        → "Cellular"
  cell_5G_stats_cfg[0].stat.RSRPCurrent   → -81
  cell_5G_stats_cfg[0].stat.RSRQCurrent   → -11
  cell_5G_stats_cfg[0].stat.SNRCurrent    → 11
  cell_5G_stats_cfg[0].stat.SignalStrengthLevel → 0-5
  cell_LTE_stats_cfg[0].stat.RSRPCurrent  → -96
  cell_LTE_stats_cfg[0].stat.RSRQCurrent  → -15
  cell_LTE_stats_cfg[0].stat.RSSICurrent  → -81
  cell_LTE_stats_cfg[0].stat.SNRCurrent   → 5
  cell_LTE_stats_cfg[0].stat.SignalStrengthLevel → 0-5

dashboard_device_info_status response (confirmed):
  device_app_status[0].SoftwareVersion    → "<version string>"
  device_app_status[0].SerialNumber       → "<serial>"
  device_app_status[0].UpTime             → <seconds since boot>
  device_cfg[]                            → list of connected LAN devices
  unread_sms[0].UnreadSMS                 → 0
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import logging
import os
from datetime import datetime
from typing import Any

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USE_HTTPS,
    CONF_USERNAME,
    DATA_5G_RSRP,
    DATA_5G_RSRQ,
    DATA_5G_SIGNAL_LEVEL,
    DATA_5G_SINR,
    DATA_CONNECTION_STATE,
    DATA_CONNECTED_DEVICES,
    DATA_ERROR,
    DATA_LAST_UPDATE,
    DATA_LTE_RSRP,
    DATA_LTE_RSRQ,
    DATA_LTE_RSSI,
    DATA_LTE_SIGNAL_LEVEL,
    DATA_LTE_SINR,
    DATA_SERIAL_NUMBER,
    DATA_SW_VERSION,
    DATA_UNREAD_SMS,
    DATA_UPTIME,
    DATA_WAN_ACTIVE,
    DATA_WAN_MODE,
    DEFAULT_USE_HTTPS,
    DOMAIN,
    LOGIN_SUCCESS_STATUS,
    PATH_DEVICE_INFO,
    PATH_LOGIN,
    PATH_LOGIN_NONCE,
    PATH_LOGIN_SALT,
    PATH_OVERVIEW,
    SCAN_INTERVAL,
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


# ── Coordinator data ──────────────────────────────────────────────────────────

def _empty_data() -> dict[str, Any]:
    return {
        DATA_5G_RSRP: None,
        DATA_5G_RSRQ: None,
        DATA_5G_SINR: None,
        DATA_5G_SIGNAL_LEVEL: None,
        DATA_LTE_RSRP: None,
        DATA_LTE_RSRQ: None,
        DATA_LTE_RSSI: None,
        DATA_LTE_SINR: None,
        DATA_LTE_SIGNAL_LEVEL: None,
        DATA_CONNECTION_STATE: None,
        DATA_WAN_MODE: None,
        DATA_WAN_ACTIVE: None,
        DATA_UPTIME: None,
        DATA_SW_VERSION: None,
        DATA_SERIAL_NUMBER: None,
        DATA_CONNECTED_DEVICES: None,
        DATA_UNREAD_SMS: None,
        DATA_LAST_UPDATE: None,
        DATA_ERROR: None,
    }


def _int_or_none(val: Any) -> int | None:
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def _str_or_none(val: Any) -> str | None:
    return str(val).strip() if val not in (None, "", "N/A", "null") else None


# ── Coordinator ───────────────────────────────────────────────────────────────

class NokiaFastMileCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Polls Nokia FastMile 5G router for signal and system data."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self._config = config_entry.data
        self._session: aiohttp.ClientSession | None = None
        self._authenticated: bool = False

    # ── lifecycle ─────────────────────────────────────────────────────────────

    async def async_setup(self) -> None:
        connector = aiohttp.TCPConnector(ssl=False)
        self._session = aiohttp.ClientSession(
            connector=connector,
            cookie_jar=aiohttp.CookieJar(),
            timeout=aiohttp.ClientTimeout(connect=10, sock_read=15),
        )

    async def async_shutdown(self) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None
        self._authenticated = False

    # ── coordinator core ──────────────────────────────────────────────────────

    async def _async_update_data(self) -> dict[str, Any]:
        last = self.data or _empty_data()
        try:
            await self._ensure_auth()
            result = dict(_empty_data())

            overview = await self._get(PATH_OVERVIEW)
            self._parse_overview(overview, result)

            device_info = await self._get(PATH_DEVICE_INFO)
            self._parse_device_info(device_info, result)

            result[DATA_LAST_UPDATE] = datetime.now().isoformat(timespec="seconds")
            result[DATA_ERROR] = None
            return result

        except aiohttp.ClientConnectorError as err:
            _LOGGER.warning("nokia_fastmile: network error — %s", err)
            return {**last, DATA_ERROR: f"Błąd sieci: {err}"}

        except asyncio.TimeoutError:
            _LOGGER.warning("nokia_fastmile: request timed out")
            return {**last, DATA_ERROR: "Timeout"}

        except aiohttp.ClientResponseError as err:
            _LOGGER.warning("nokia_fastmile: HTTP %s — %s", err.status, err.message)
            if err.status in (401, 403):
                self._authenticated = False
            return {**last, DATA_ERROR: f"HTTP {err.status}"}

        except ValueError as err:
            _LOGGER.warning("nokia_fastmile: JSON decode error — %s", err)
            self._authenticated = False
            return {**last, DATA_ERROR: "Nieprawidłowa odpowiedź"}

    # ── auth ──────────────────────────────────────────────────────────────────

    def _base_url(self) -> str:
        host = self._config[CONF_HOST]
        scheme = "https" if self._config.get(CONF_USE_HTTPS, DEFAULT_USE_HTTPS) else "http"
        return f"{scheme}://{host}"

    async def _ensure_auth(self) -> None:
        if not self._authenticated:
            await self._login()

    async def _login(self) -> None:
        assert self._session is not None
        base = self._base_url()
        username = self._config[CONF_USERNAME]
        password = self._config[CONF_PASSWORD]

        # Step 1 — nonce + crypto params
        async with self._session.get(base + PATH_LOGIN_NONCE) as r:
            r.raise_for_status()
            nonce_data = await r.json(content_type=None)
        _LOGGER.debug("nokia_fastmile: nonce_data=%s", nonce_data)

        nonce_b64: str = nonce_data["nonce"]
        random_key: str = str(nonce_data.get("randomKey", ""))
        iterations: int = int(nonce_data.get("iterations", 1))
        nonce_bytes = _std_b64decode(nonce_b64)

        # Step 2 — salt (empty on this firmware; fetch to maintain correct session state)
        async with self._session.get(base + PATH_LOGIN_SALT) as r:
            r.raise_for_status()

        # Step 3 — compute PBKDF2-HMAC-SHA256 hashes and POST
        #
        # PBKDF2(key=value, salt=nonce_bytes, iterations, dklen=32) → 32 bytes
        # Encoded with Nokia base64url ('.' replaces '=' padding).
        # enckey / enciv are random 16-byte session placeholders (browser-generated each login).
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

        async with self._session.post(base + PATH_LOGIN, json=payload) as r:
            if r.status == LOGIN_SUCCESS_STATUS:
                self._authenticated = True
                _LOGGER.info("nokia_fastmile: login successful (HTTP %s)", r.status)
                return
            body = await r.text()
            _LOGGER.error(
                "nokia_fastmile: login failed — HTTP %s body=%.300s", r.status, body
            )
            raise aiohttp.ClientResponseError(
                r.request_info, r.history, status=r.status, message="Login failed"
            )

    # ── HTTP helpers ──────────────────────────────────────────────────────────

    async def _get(self, path: str) -> dict[str, Any]:
        assert self._session is not None
        async with self._session.get(self._base_url() + path) as r:
            if r.status in (401, 403):
                self._authenticated = False
                await self._login()
                async with self._session.get(self._base_url() + path) as r2:
                    r2.raise_for_status()
                    return await r2.json(content_type=None) or {}
            r.raise_for_status()
            return await r.json(content_type=None) or {}

    # ── parsers ───────────────────────────────────────────────────────────────

    def _parse_overview(self, raw: dict[str, Any], out: dict[str, Any]) -> None:
        # connection_status[0].ConnectionStatus (1 = connected)
        conn_list = raw.get("connection_status") or []
        if conn_list:
            out[DATA_CONNECTION_STATE] = (
                "Connected" if conn_list[0].get("ConnectionStatus") == 1 else "Disconnected"
            )

        # WAN[0].Mode / ActiveWAN
        wan_list = raw.get("WAN") or []
        if wan_list:
            out[DATA_WAN_MODE] = _str_or_none(wan_list[0].get("Mode"))
            out[DATA_WAN_ACTIVE] = _str_or_none(wan_list[0].get("ActiveWAN"))

        # 5G: cell_5G_stats_cfg[0].stat
        stats_5g = raw.get("cell_5G_stats_cfg") or []
        if stats_5g:
            stat = stats_5g[0].get("stat") or {}
            out[DATA_5G_RSRP] = _int_or_none(stat.get("RSRPCurrent"))
            out[DATA_5G_RSRQ] = _int_or_none(stat.get("RSRQCurrent"))
            out[DATA_5G_SINR] = _int_or_none(stat.get("SNRCurrent"))
            out[DATA_5G_SIGNAL_LEVEL] = _int_or_none(stat.get("SignalStrengthLevel"))

        # LTE: cell_LTE_stats_cfg[0].stat
        stats_lte = raw.get("cell_LTE_stats_cfg") or []
        if stats_lte:
            stat = stats_lte[0].get("stat") or {}
            out[DATA_LTE_RSRP] = _int_or_none(stat.get("RSRPCurrent"))
            out[DATA_LTE_RSRQ] = _int_or_none(stat.get("RSRQCurrent"))
            out[DATA_LTE_RSSI] = _int_or_none(stat.get("RSSICurrent"))
            out[DATA_LTE_SINR] = _int_or_none(stat.get("SNRCurrent"))
            out[DATA_LTE_SIGNAL_LEVEL] = _int_or_none(stat.get("SignalStrengthLevel"))

    def _parse_device_info(self, raw: dict[str, Any], out: dict[str, Any]) -> None:
        # device_app_status[0]
        app_list = raw.get("device_app_status") or []
        if app_list:
            app = app_list[0]
            out[DATA_UPTIME] = _int_or_none(app.get("UpTime"))
            out[DATA_SW_VERSION] = _str_or_none(app.get("SoftwareVersion"))
            out[DATA_SERIAL_NUMBER] = _str_or_none(app.get("SerialNumber"))

        # device_cfg[] — connected LAN clients
        out[DATA_CONNECTED_DEVICES] = len(raw.get("device_cfg") or [])

        # unread_sms[0].UnreadSMS
        sms_list = raw.get("unread_sms") or []
        if sms_list:
            out[DATA_UNREAD_SMS] = _int_or_none(sms_list[0].get("UnreadSMS"))

    # ── public helpers ────────────────────────────────────────────────────────

    async def test_connection(self) -> bool:
        try:
            await self._ensure_auth()
            return True
        except Exception:  # noqa: BLE001
            return False
