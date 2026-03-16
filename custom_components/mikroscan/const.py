"""Constants for the Mikroscan Home Assistant integration."""

DOMAIN = "mikroscan"
PLATFORMS = ["sensor", "button"]
FRONTEND_CARD_URL = "/api/mikroscan/static/mikroscan-card.js"

CONF_SCAN_RANGE = "scan_range"
CONF_WEB_PORT = "web_port"

DEFAULT_HOST = "127.0.0.1"
DEFAULT_WEB_PORT = 8080
DEFAULT_SCAN_RANGE = ""
DEFAULT_UPDATE_INTERVAL = 15

SERVICE_SCAN = "scan"
SERVICE_GENERATE_TOPOLOGY = "generate_topology"

ATTR_IP_RANGE = "ip_range"

DATA_CLIENT = "client"
DATA_COORDINATOR = "coordinator"
