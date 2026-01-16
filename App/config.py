import os
from dataclasses import dataclass

# ---- Cortex ----
CORTEX_URL = os.getenv("CORTEX_URL", "wss://localhost:6868")
CLIENT_ID = os.getenv("EMOTIV_CLIENT_ID", "dikQvTTxwaSSHBL4HhFpjbFhNW0LDVJ64A9I2TmY")
CLIENT_SECRET = os.getenv("EMOTIV_CLIENT_SECRET", "jqiDiUlE1dycz9LmaeiThEWbTNhNwsLy8VtnLkeUqRL6S9iIuREhpV76ZCWk0fhr7w7pDOIIzfKcqWd5Znb0y4MTkLJyn0H7f6DEY8EarRGp7MJw3x7JJi1GauNLLM1t")
DEBIT = int(os.getenv("EMOTIV_DEBIT", "10"))  # >0 pour éviter -32019

PROFILE_NAME = os.getenv("EMOTIV_PROFILE", "popoche")
LOAD_PROFILE = os.getenv("EMOTIV_LOAD_PROFILE", "1") == "1"

# ---- Servo/PCA9685 ----
PCA_FREQUENCY_HZ = int(os.getenv("PCA_FREQUENCY_HZ", "330"))

@dataclass(frozen=True)
class MotorConfig:
    channel: int
    stop_us: int
    open_us: int
    close_us: int
    # workaround mécanique: frein bref quand on stop après open
    brake_on_stop_from_open: bool = True
    brake_us: int = 1000
    brake_time_s: float = 0.10

# Reprise de vos valeurs (open=3000, stop=2000, close=1000) + mapping channels.
MOTORS = {
    "thumb":  MotorConfig(channel=0,  stop_us=2000, open_us=3000, close_us=1000),
    "index":  MotorConfig(channel=3,  stop_us=2000, open_us=3000, close_us=1000),
    "middle": MotorConfig(channel=7,  stop_us=2000, open_us=3000, close_us=1000),
    "ring":   MotorConfig(channel=11, stop_us=2000, open_us=3000, close_us=1000),
    "pinky":  MotorConfig(channel=15, stop_us=2000, open_us=3000, close_us=1000),
}
FINGERS = list(MOTORS.keys())

# ---- Mapping Mental Commands -> main ----
POW_ON = float(os.getenv("EMOTIV_POW_ON", "0.55"))
POW_OFF = float(os.getenv("EMOTIV_POW_OFF", "0.45"))   # hystérésis
MIN_COMMAND_INTERVAL_S = float(os.getenv("MIN_CMD_INTERVAL", "0.12"))  # anti-spam