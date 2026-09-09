from __future__ import annotations

from datetime import timedelta

DOMAIN = "nokia_fastmile"
NAME = "Nokia FastMile 5G"

CONF_HOST = "host"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_USE_HTTPS = "use_https"

DEFAULT_HOST = "192.168.192.1"
DEFAULT_USERNAME = "admin"
DEFAULT_USE_HTTPS = False

SCAN_INTERVAL = timedelta(seconds=30)
REQUEST_TIMEOUT = 10

# CGI endpoints (verified via DevTools on firmware 1.2302.00.0355)
PATH_LOGIN_NONCE = "/login_web_app.cgi?nonce"
PATH_LOGIN_SALT = "/login_web_app.cgi?salt"
PATH_LOGIN = "/login_web_app.cgi"
PATH_OVERVIEW = "/overview_get_web_app.cgi"
PATH_DEVICE_INFO = "/dashboard_device_info_status_web_app.cgi"
PATH_STATUS = "/status_get_web_app.cgi"
PATH_STATISTICS = "/statistics_status_web_app.cgi"
PATH_CHECK_EXPIRE = "/check_expire_web_app.cgi"
PATH_REBOOT = "/reboot_web_app.cgi"

# Nokia-specific HTTP status codes for successful login
LOGIN_SUCCESS_STATUS = (200, 299)

# ── Coordinator data keys ──────────────────────────────────────────────────────
# 5G signal (from overview_get_web_app.cgi → cell_5G_stats_cfg[0].stat)
DATA_5G_RSRP = "5g_rsrp"
DATA_5G_RSRQ = "5g_rsrq"
DATA_5G_SINR = "5g_sinr"
DATA_5G_SIGNAL_LEVEL = "5g_signal_level"
DATA_5G_RSRP_STRENGTH_INDEX = "5g_rsrp_strength_index"
DATA_5G_PHYSICAL_CELL_ID = "5g_physical_cell_id"
DATA_5G_DOWNLINK_ARFCN = "5g_downlink_arfcn"
DATA_5G_BAND = "5g_band"

# LTE signal (from overview_get_web_app.cgi → cell_LTE_stats_cfg[0].stat)
DATA_LTE_RSRP = "lte_rsrp"
DATA_LTE_RSRQ = "lte_rsrq"
DATA_LTE_RSSI = "lte_rssi"
DATA_LTE_SINR = "lte_sinr"
DATA_LTE_SIGNAL_LEVEL = "lte_signal_level"
DATA_LTE_RSRP_STRENGTH_INDEX = "lte_rsrp_strength_index"
DATA_LTE_PHYSICAL_CELL_ID = "lte_physical_cell_id"
DATA_LTE_DOWNLINK_EARFCN = "lte_downlink_earfcn"
DATA_LTE_BAND = "lte_band"

# Connection / WAN (from overview_get_web_app.cgi)
DATA_CONNECTION_STATE = "connection_state"
DATA_WAN_MODE = "wan_mode"
DATA_WAN_ACTIVE = "wan_active"
DATA_APN = "apn"
DATA_CELLULAR_CONNECTION_STATE = "cellular_connection_state"
DATA_CELLULAR_IPV4 = "cellular_ipv4"
DATA_ETHERNET_STATUS = "ethernet_status"

# Transfer data (from status_get_web_app.cgi)
DATA_CELLULAR_BYTES_RECEIVED = "cellular_bytes_received"
DATA_CELLULAR_BYTES_SENT = "cellular_bytes_sent"
DATA_ETHERNET_BYTES_RECEIVED = "ethernet_bytes_received"
DATA_ETHERNET_BYTES_SENT = "ethernet_bytes_sent"
DATA_ETHERNET_PACKETS_RECEIVED = "ethernet_packets_received"
DATA_ETHERNET_PACKETS_SENT = "ethernet_packets_sent"

# Device info (from dashboard_device_info_status_web_app.cgi)
DATA_UPTIME = "uptime"
DATA_SW_VERSION = "sw_version"
DATA_SERIAL_NUMBER = "serial_number"
DATA_CONNECTED_DEVICES = "connected_devices"
DATA_UNREAD_SMS = "unread_sms"

# Meta
DATA_LAST_UPDATE = "last_update"
DATA_ERROR = "error"
