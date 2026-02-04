"""Constants for Radialight Cloud integration."""

DOMAIN = "radialight_cloud"
INTEGRATION_VERSION = "0.2.0"

# Endpoints
RADIALIGHT_BASE_URL = "https://myradialight-fe-prod.opengate.it"
FIREBASE_TOKEN_URL = "https://securetoken.googleapis.com/v1/token"

# Default values
DEFAULT_POLLING_INTERVAL = 60  # seconds
POLL_JITTER_SECONDS = 10
LOG_RATE_LIMIT_SECONDS = 300

# Temperature limits (in °C)
MIN_TEMP = 7.0
MAX_TEMP = 30.0
TEMP_STEP = 0.5

# Preset modes
PRESET_PROGRAM = "program"
PRESET_COMFORT = "comfort"
PRESET_ECO = "eco"

# Configuration keys
CONF_FIREBASE_API_KEY = "firebase_api_key"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_POLLING_INTERVAL = "polling_interval"
CONF_ENABLE_PRODUCT_ENTITIES = "enable_product_entities"
DEFAULT_ENABLE_PRODUCT_ENTITIES = True
CONF_ENABLE_USAGE_SENSORS = "enable_usage_sensors"
DEFAULT_ENABLE_USAGE_SENSORS = True

CONF_SHOW_ADVANCED_ENTITIES = "show_advanced_entities"
DEFAULT_SHOW_ADVANCED_ENTITIES = False

CONF_USAGE_SCALE = "usage_scale"
USAGE_SCALE_RAW = "raw"
USAGE_SCALE_WH = "wh"
USAGE_SCALE_DECIWH = "deciwh"
DEFAULT_USAGE_SCALE = USAGE_SCALE_DECIWH

# Data keys for storing in hass.data[DOMAIN][entry.entry_id]
DATA_API = "api"
DATA_COORDINATOR = "coordinator"
