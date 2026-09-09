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
  /status_get_web_app.cgi
  /statistics_status_web_app.cgi
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
import json
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
    DATA_5G_BAND,
    DATA_5G_DOWNLINK_ARFCN,
    DATA_5G_PHYSICAL_CELL_ID,
    DATA_5G_RSRP_STRENGTH_INDEX,
    DATA_5G_RSRQ,
    DATA_5G_SIGNAL_LEVEL,
    DATA_5G_SINR,
    DATA_CELLULAR_BYTES_RECEIVED,
    DATA_CELLULAR_BYTES_SENT,
    DATA_CELLULAR_CONNECTION_STATE,
    DATA_CELLULAR_IPV4,
    DATA_CONNECTION_STATE,
    DATA_CONNECTED_DEVICES,
    DATA_ETHERNET_BYTES_RECEIVED,
    DATA_ETHERNET_BYTES_SENT,
    DATA_ETHERNET_PACKETS_RECEIVED,
    DATA_ETHERNET_PACKETS_SENT,
    DATA_ETHERNET_STATUS,
    DATA_ERROR,
    DATA_LAST_UPDATE,
    DATA_APN,
    DATA_LTE_RSRP,
    DATA_LTE_BAND,
    DATA_LTE_DOWNLINK_EARFCN,
    DATA_LTE_PHYSICAL_CELL_ID,
    DATA_LTE_RSRP_STRENGTH_INDEX,
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
    PATH_CHECK_EXPIRE,
    PATH_DEVICE_INFO,
    PATH_LOGIN,
    PATH_LOGIN_NONCE,
    PATH_LOGIN_SALT,
    PATH_OVERVIEW,
    PATH_STATISTICS,
    PATH_STATUS,
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


def _sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _sha256_url(value: str, nonce: str) -> str:
    return _nokia_b64encode(hashlib.sha256((value + nonce).encode()).digest())


# ── Coordinator data ──────────────────────────────────────────────────────────

def _empty_data() -> dict[str, Any]:
    return {
        DATA_5G_RSRP: None,
        DATA_5G_RSRQ: None,
        DATA_5G_SINR: None,
        DATA_5G_SIGNAL_LEVEL: None,
        DATA_5G_RSRP_STRENGTH_INDEX: None,
        DATA_5G_PHYSICAL_CELL_ID: None,
        DATA_5G_DOWNLINK_ARFCN: None,
        DATA_5G_BAND: None,
        DATA_LTE_RSRP: None,
        DATA_LTE_RSRQ: None,
        DATA_LTE_RSSI: None,
        DATA_LTE_SINR: None,
        DATA_LTE_SIGNAL_LEVEL: None,
        DATA_LTE_RSRP_STRENGTH_INDEX: None,
        DATA_LTE_PHYSICAL_CELL_ID: None,
        DATA_LTE_DOWNLINK_EARFCN: None,
        DATA_LTE_BAND: None,
        DATA_CONNECTION_STATE: None,
        DATA_WAN_MODE: None,
        DATA_WAN_ACTIVE: None,
        DATA_APN: None,
        DATA_CELLULAR_CONNECTION_STATE: None,
        DATA_CELLULAR_IPV4: None,
        DATA_ETHERNET_STATUS: None,
        DATA_CELLULAR_BYTES_RECEIVED: None,
        DATA_CELLULAR_BYTES_SENT: None,
        DATA_ETHERNET_BYTES_RECEIVED: None,
        DATA_ETHERNET_BYTES_SENT: None,
        DATA_ETHERNET_PACKETS_RECEIVED: None,
        DATA_ETHERNET_PACKETS_SENT: None,
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


def _json_or_raise(text: str, path: str) -> dict[str, Any]:
    try:
        data = json.loads(text)
    except ValueError:
        _LOGGER.debug(
            "nokia_fastmile: non-JSON response from %s: %.200s",
            path,
            text,
        )
        raise
    return data or {}


def _has_session_cookie(session: aiohttp.ClientSession) -> bool:
    if session.cookie_jar is None:
        return False
    return any(
        cookie.key.lower() == "sid"
        and cookie.value
        and cookie.value.lower() != "deleted"
        for cookie in session.cookie_jar
    )


def _session_cookie_value(session: aiohttp.ClientSession) -> str | None:
    if session.cookie_jar is None:
        return None
    for cookie in session.cookie_jar:
        if cookie.key.lower() == "sid" and cookie.value and cookie.value.lower() != "deleted":
            return cookie.value
    return None


def _login_body_session(body: str) -> tuple[str, str | None] | None:
    try:
        data = json.loads(body)
    except ValueError:
        return None
    if data.get("result") != 0:
        return None
    sid = _str_or_none(data.get("sid"))
    if sid is None:
        return None
    return sid, _str_or_none(data.get("token"))


def _redact_login_body(body: str) -> str:
    try:
        data = json.loads(body)
    except ValueError:
        return body[:120]
    for key in ("sid", "token"):
        if key in data:
            data[key] = "<redacted>"
    return json.dumps(data, separators=(",", ":"))


def _build_login_payload(
    username: str,
    password: str,
    nonce_data: dict[str, Any],
    alati: str,
    *,
    dotted_nonce: bool = True,
) -> dict[str, str]:
    nonce_b64: str = nonce_data["nonce"]
    random_key: str = str(nonce_data.get("randomKey", ""))
    iterations: int = int(nonce_data.get("iterations", 1))
    nonce_bytes = _std_b64decode(nonce_b64)
    escaped_nonce = _nokia_b64encode(nonce_bytes) if dotted_nonce else nonce_b64
    password_hash = _sha256_hex(alati + password) if iterations >= 1 else alati + password

    for _ in range(1, iterations):
        password_hash = hashlib.sha256(bytes.fromhex(password_hash)).hexdigest()

    user_password_hash = _sha256_hex(username + password_hash.lower())

    return {
        "userhash": _sha256_url(username, nonce_b64),
        "RandomKeyhash": _sha256_url(random_key, nonce_b64),
        "response": _sha256_url(user_password_hash, nonce_b64),
        "nonce": escaped_nonce,
        "enckey": _nokia_b64encode(os.urandom(16)),
        "enciv": _nokia_b64encode(os.urandom(16)),
    }


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
        self._sid: str | None = None
        self._token: str | None = None
        self._login_retry_count: int = 0
        self._max_login_retries: int = 2

    # ── lifecycle ─────────────────────────────────────────────────────────────

    async def async_setup(self) -> None:
        connector = aiohttp.TCPConnector(ssl=False)
        cookie_jar = aiohttp.CookieJar(unsafe=True)
        self._session = aiohttp.ClientSession(
            connector=connector,
            cookie_jar=cookie_jar,
            timeout=aiohttp.ClientTimeout(connect=10, sock_read=15),
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/152.0.0.0 Safari/537.36"
                ),
            },
        )
        _LOGGER.debug("nokia_fastmile: session created with CookieJar enabled for IP hosts")

    async def async_shutdown(self) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None
        self._authenticated = False
        self._sid = None
        self._token = None

    # ── coordinator core ──────────────────────────────────────────────────────

    async def _async_update_data(self) -> dict[str, Any]:
        _LOGGER.debug("nokia_fastmile: starting data update")
        last = self.data or _empty_data()
        self._login_retry_count = 0  # Reset retry counter at start of update cycle
        try:
            await self._ensure_auth()
            result = dict(_empty_data())

            overview = await self._get(PATH_OVERVIEW)
            _LOGGER.debug("nokia_fastmile: overview data: %s", overview)
            self._parse_overview(overview, result)

            device_info = await self._get(PATH_DEVICE_INFO)
            _LOGGER.debug("nokia_fastmile: device_info data: %s", device_info)
            self._parse_device_info(device_info, result)

            await self._touch_session()

            try:
                status = await self._get(PATH_STATUS)
                _LOGGER.debug("nokia_fastmile: status data: %s", status)
                self._parse_overview(status, result)
                self._parse_status(status, result)
            except aiohttp.ClientResponseError as err:
                _LOGGER.debug(
                    "nokia_fastmile: optional status endpoint unavailable (HTTP %s)",
                    err.status,
                )
            except ValueError as err:
                _LOGGER.debug(
                    "nokia_fastmile: optional status endpoint returned invalid JSON: %s",
                    err,
                )

            if self._missing_transfer_data(result):
                try:
                    statistics = await self._get(PATH_STATISTICS)
                    _LOGGER.debug("nokia_fastmile: statistics data: %s", statistics)
                    self._parse_statistics(statistics, result)
                except aiohttp.ClientResponseError as err:
                    _LOGGER.debug(
                        "nokia_fastmile: optional statistics endpoint unavailable (HTTP %s)",
                        err.status,
                    )
                except ValueError as err:
                    _LOGGER.debug(
                        "nokia_fastmile: optional statistics endpoint returned invalid JSON: %s",
                        err,
                    )

            result[DATA_LAST_UPDATE] = datetime.now().isoformat(timespec="seconds")
            result[DATA_ERROR] = None
            _LOGGER.debug("nokia_fastmile: data update successful")
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

        last_request_info = None
        last_history = ()
        last_status = 0

        for mode, dotted_nonce in (
            ("json", True),
            ("json", False),
            ("form", True),
            ("form", False),
        ):
            self._session.cookie_jar.clear()
            async with self._session.get(
                base + PATH_LOGIN_NONCE,
                headers=self._request_headers(),
            ) as r:
                r.raise_for_status()
                nonce_data = await r.json(content_type=None) or {}
            _LOGGER.debug("nokia_fastmile: nonce_data=%s", nonce_data)

            async with self._session.get(
                (
                    base
                    + PATH_LOGIN_SALT
                    + f"&userhash={_sha256_url(username, nonce_data['nonce'])}"
                    + f"&nonce={_nokia_b64encode(_std_b64decode(nonce_data['nonce']))}"
                ),
                headers=self._request_headers(),
            ) as r:
                r.raise_for_status()
                salt_data = await r.json(content_type=None) or {}
                _LOGGER.debug("nokia_fastmile: salt fetch completed status=%s", r.status)

            payload = _build_login_payload(
                username,
                password,
                nonce_data,
                str(salt_data.get("alati", "")),
                dotted_nonce=dotted_nonce,
            )
            if mode == "json":
                post_kwargs = {
                    "json": payload,
                    "headers": self._request_headers(content_type=None),
                }
            else:
                post_kwargs = {
                    "data": payload,
                    "headers": self._request_headers(),
                }

            async with self._session.post(base + PATH_LOGIN, **post_kwargs) as r:
                last_request_info = r.request_info
                last_history = r.history
                last_status = r.status
                body = await r.text()
                login_session = _login_body_session(body)
                cookie_names = [c.key for c in self._session.cookie_jar] if self._session.cookie_jar else []
                _LOGGER.debug(
                    "nokia_fastmile: login attempt mode=%s nonce=%s status=%s cookies=%s body=%.120s",
                    mode,
                    "dotted" if dotted_nonce else "raw",
                    r.status,
                    cookie_names,
                    _redact_login_body(body),
                )
                if r.status in LOGIN_SUCCESS_STATUS and (
                    login_session is not None or _has_session_cookie(self._session)
                ):
                    if login_session is not None:
                        self._sid, self._token = login_session
                    else:
                        self._sid = _session_cookie_value(self._session)
                        self._token = None
                    self._authenticated = True
                    _LOGGER.info(
                        "nokia_fastmile: login successful with %s payload, %s nonce (HTTP %s)",
                        mode,
                        "dotted" if dotted_nonce else "raw",
                        r.status,
                    )
                    return

        raise aiohttp.ClientResponseError(
            last_request_info,
            last_history,
            status=last_status,
            message="Login failed",
        )

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
            _LOGGER.debug("nokia_fastmile: salt fetch completed, headers=%s", 
                         dict(r.headers) if r.status == 200 else None)

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

        async with self._session.post(
            base + PATH_LOGIN,
            data=payload,
            headers={
                "Accept": "application/json, text/plain, */*",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        ) as r:
            _LOGGER.debug("nokia_fastmile: login response status=%s headers=%s", 
                         r.status, dict(r.headers))
            
            if r.status in LOGIN_SUCCESS_STATUS and _has_session_cookie(self._session):
                # Debug: log cookies
                if self._session.cookie_jar:
                    _LOGGER.debug(
                        "nokia_fastmile: cookie names after login: %s",
                        [c.key for c in self._session.cookie_jar],
                    )
                
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
        try:
            async with self._session.get(
                self._base_url() + path,
                headers=self._request_headers(),
            ) as r:
                if r.status in (401, 403):
                    _LOGGER.debug("nokia_fastmile: received %s on path %s, resetting auth", r.status, path)
                    self._authenticated = False
                    self._sid = None
                    self._token = None
                    
                    # Only retry once per endpoint to avoid infinite loops
                    if self._login_retry_count < self._max_login_retries:
                        self._login_retry_count += 1
                        _LOGGER.info("nokia_fastmile: attempting re-login for %s (%d/%d)", 
                                   path, self._login_retry_count, self._max_login_retries)
                        await self._login()
                        
                        # Retry the request with fresh login
                        async with self._session.get(
                            self._base_url() + path,
                            headers=self._request_headers(),
                        ) as r2:
                            if r2.status in (401, 403):
                                _LOGGER.warning("nokia_fastmile: still %s after re-login on path %s", r2.status, path)
                                self._sid = None
                                self._token = None
                                r2.raise_for_status()
                            return _json_or_raise(await r2.text(), path)
                    else:
                        _LOGGER.warning("nokia_fastmile: max retries exceeded for path %s", path)
                        r.raise_for_status()
                
                r.raise_for_status()
                return _json_or_raise(await r.text(), path)
        
        except aiohttp.ClientResponseError:
            raise
        except Exception as err:
            _LOGGER.error("nokia_fastmile: unexpected error in _get(%s): %s", path, err)
            raise

    async def _touch_session(self) -> None:
        assert self._session is not None
        try:
            async with self._session.get(
                self._base_url() + PATH_CHECK_EXPIRE,
                headers=self._request_headers(),
            ) as r:
                body = await r.text()
                _LOGGER.debug(
                    "nokia_fastmile: session check status=%s body=%.80s",
                    r.status,
                    body,
                )
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            _LOGGER.debug("nokia_fastmile: session check skipped: %s", err)

    def _request_headers(self, *, content_type: str | None = "application/x-www-form-urlencoded") -> dict[str, str]:
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": f"{self._base_url()}/web_whw/",
        }
        if content_type is not None:
            headers["Content-Type"] = content_type
        if self._sid:
            headers["Cookie"] = f"sid={self._sid}"
        return headers

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
            out[DATA_5G_RSRP_STRENGTH_INDEX] = _int_or_none(stat.get("RSRPStrengthIndexCurrent"))
            out[DATA_5G_PHYSICAL_CELL_ID] = _str_or_none(stat.get("PhysicalCellID"))
            out[DATA_5G_DOWNLINK_ARFCN] = _int_or_none(stat.get("Downlink_NR_ARFCN"))
            out[DATA_5G_BAND] = _str_or_none(stat.get("Band"))

        # LTE: cell_LTE_stats_cfg[0].stat
        stats_lte = raw.get("cell_LTE_stats_cfg") or []
        if stats_lte:
            stat = stats_lte[0].get("stat") or {}
            out[DATA_LTE_RSRP] = _int_or_none(stat.get("RSRPCurrent"))
            out[DATA_LTE_RSRQ] = _int_or_none(stat.get("RSRQCurrent"))
            out[DATA_LTE_RSSI] = _int_or_none(stat.get("RSSICurrent"))
            out[DATA_LTE_SINR] = _int_or_none(stat.get("SNRCurrent"))
            out[DATA_LTE_SIGNAL_LEVEL] = _int_or_none(stat.get("SignalStrengthLevel"))
            out[DATA_LTE_RSRP_STRENGTH_INDEX] = _int_or_none(stat.get("RSRPStrengthIndexCurrent"))
            out[DATA_LTE_PHYSICAL_CELL_ID] = _str_or_none(stat.get("PhysicalCellID"))
            out[DATA_LTE_DOWNLINK_EARFCN] = _int_or_none(stat.get("DownlinkEarfcn"))
            out[DATA_LTE_BAND] = _str_or_none(stat.get("Band"))

    def _parse_status(self, raw: dict[str, Any], out: dict[str, Any]) -> None:
        apn_list = raw.get("apn_cfg") or []
        if apn_list:
            apn = apn_list[0]
            out[DATA_APN] = _str_or_none(apn.get("APN"))
            out[DATA_CELLULAR_CONNECTION_STATE] = _str_or_none(apn.get("X_ALU_COM_ConnectionState"))
            out[DATA_CELLULAR_IPV4] = _str_or_none(apn.get("X_ALU_COM_IPAddressV4"))

        # cellular_stats[0]
        cellular_list = raw.get("cellular_stats") or []
        if cellular_list:
            cellular = cellular_list[0]
            out[DATA_CELLULAR_BYTES_RECEIVED] = _int_or_none(cellular.get("BytesReceived"))
            out[DATA_CELLULAR_BYTES_SENT] = _int_or_none(cellular.get("BytesSent"))

        # ethernet_stats[0].stat
        ethernet_list = raw.get("ethernet_stats") or []
        if ethernet_list:
            ethernet = ethernet_list[0]
            out[DATA_ETHERNET_STATUS] = _str_or_none(ethernet.get("Status"))
            stat = ethernet.get("stat") or {}
            out[DATA_ETHERNET_BYTES_RECEIVED] = _int_or_none(stat.get("BytesReceived"))
            out[DATA_ETHERNET_BYTES_SENT] = _int_or_none(stat.get("BytesSent"))
            out[DATA_ETHERNET_PACKETS_RECEIVED] = _int_or_none(stat.get("PacketsReceived"))
            out[DATA_ETHERNET_PACKETS_SENT] = _int_or_none(stat.get("PacketsSent"))

    def _parse_statistics(self, raw: dict[str, Any], out: dict[str, Any]) -> None:
        lan_list = raw.get("LAN") or []
        if lan_list:
            lan = lan_list[0]
            out[DATA_ETHERNET_BYTES_RECEIVED] = _int_or_none(lan.get("BytesReceived"))
            out[DATA_ETHERNET_BYTES_SENT] = _int_or_none(lan.get("BytesSent"))
            out[DATA_ETHERNET_PACKETS_RECEIVED] = _int_or_none(lan.get("PacketsReceived"))
            out[DATA_ETHERNET_PACKETS_SENT] = _int_or_none(lan.get("PacketsSent"))

        for wan_key in ("WAN", "ethWAN"):
            wan_list = raw.get(wan_key) or []
            if not wan_list:
                continue
            services = wan_list[0].get("Service") or []
            if not services:
                continue
            service = services[0]
            out[DATA_CELLULAR_BYTES_RECEIVED] = _int_or_none(service.get("EthernetBytesReceived"))
            out[DATA_CELLULAR_BYTES_SENT] = _int_or_none(service.get("EthernetBytesSent"))
            break

    def _missing_transfer_data(self, data: dict[str, Any]) -> bool:
        return any(
            data.get(key) is None
            for key in (
                DATA_CELLULAR_BYTES_RECEIVED,
                DATA_CELLULAR_BYTES_SENT,
                DATA_ETHERNET_BYTES_RECEIVED,
                DATA_ETHERNET_BYTES_SENT,
                DATA_ETHERNET_PACKETS_RECEIVED,
                DATA_ETHERNET_PACKETS_SENT,
            )
        )

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
