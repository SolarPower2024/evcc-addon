"""Constants of evcc Peak Fronius."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "evcc_peak_fronius"
DEFAULT_NAME = "evcc Peak Fronius"

PLATFORMS: list[Platform] = [
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

# Entities of fronius_modbus (and the meter) picked in the config flow.
CONF_GRID_POWER = "grid_power"
CONF_GRID_INVERT = "grid_invert"
CONF_BATTERY_POWER = "battery_power"
CONF_BATTERY_INVERT = "battery_invert"
# optional: fronius_modbus has a discharge and a charge power sensor, both
# positive; the charge power is subtracted
CONF_BATTERY_CHARGE_POWER = "battery_charge_power"
CONF_SOC = "soc"
CONF_MODE = "mode"
CONF_DISCHARGE_LIMIT = "discharge_limit"
CONF_GRID_CHARGE = "grid_charge"
CONF_RESET_BUTTON = "reset_button"

# Options of the fronius_modbus select "Storage Control Mode" this
# integration uses. They are the select's state keys, not translated.
MODE_AUTO = "Auto"
MODE_DISCHARGE_LIMIT = "Discharge Limit"
MODE_GRID_CHARGE = "Charge from Grid"
MODE_BLOCK_DISCHARGE = "Block Discharging"
REQUIRED_MODES = (MODE_AUTO, MODE_DISCHARGE_LIMIT, MODE_GRID_CHARGE, MODE_BLOCK_DISCHARGE)

# Requests evcc sets on the own select entity.
REQUEST_NORMAL = "normal"
REQUEST_GRID_CHARGE = "grid_charge"
REQUEST_HOLD = "hold"
REQUESTS = [REQUEST_NORMAL, REQUEST_GRID_CHARGE, REQUEST_HOLD]

# Keys of the own entities, also the suffix of their entity ids.
KEY_PEAK_SHAVING = "peak_shaving"
KEY_LIMIT = "limit"
KEY_SOC_THRESHOLD = "soc_threshold"
KEY_REQUEST = "request"
KEY_GRID_CHARGE_POWER = "grid_charge_power"
KEY_STATUS = "status"

# Control.
EVAL_INTERVAL_S = 5  # periodic evaluation besides the state events
MIN_EVAL_GAP_S = 2.0  # at most one evaluation per 2 s
WRITE_TOLERANCE_W = 50  # smaller changes are not written
LOWER_INTERVAL_S = 10  # a lower discharge limit at most every 10 s
MIN_WRITE_GAP_S = 2  # at most one write to the inverter per 2 s
MODE_RETRY_S = 10  # wait this long for a written mode to show
MODE_ATTEMPTS_BEFORE_RESET = 3
HYSTERESIS_PCT = 2  # leave the reserve only 2 % above the threshold
METER_STALE_S = 30  # grid power older than this counts as an outage
# fronius_modbus writes the Web API charge sources on every switch to Charge from
# Grid and reconnects Modbus; for up to 30 s its sensors repeat the last values
RECONNECT_S = 30
HEARTBEAT_GRACE_S = 120  # evcc has 2 min of each quarter to write the limit
QUARTER_S = 15 * 60
POWER_STEP_W = 10  # fronius_modbus takes powers in multiples of 10 W

STORAGE_VERSION = 1
