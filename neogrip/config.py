import os
from dataclasses import dataclass

def _getenv_required(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise RuntimeError(f"Variable d'environnement manquante: {name}")
    return v

def _getenv_bool(name: str, default: str = "0") -> bool:
    return os.getenv(name, default) == "1"

# ---- Cortex ----
CORTEX_URL = os.getenv("CORTEX_URL", "wss://localhost:6868")

CLIENT_ID = _getenv_required("EMOTIV_CLIENT_ID")
CLIENT_SECRET = _getenv_required("EMOTIV_CLIENT_SECRET")
PROFILE_NAME = _getenv_required("EMOTIV_PROFILE")

DEBIT = int(os.getenv("EMOTIV_DEBIT", "10"))  # >0 pour éviter -32019
LOAD_PROFILE = _getenv_bool("EMOTIV_LOAD_PROFILE", "1")

# ---- Servo/PCA9685 ----
PCA_FREQUENCY_HZ = int(os.getenv("PCA_FREQUENCY_HZ", "330"))

@dataclass(frozen=True)
class MotorConfig:
    channel: int
    stop_us: int
    open_us: int
    close_us: int
    brake_on_stop_from_open: bool = True
    brake_us: int = 1000
    brake_time_s: float = 0.10

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
POW_OFF = float(os.getenv("EMOTIV_POW_OFF", "0.45"))
MIN_COMMAND_INTERVAL_S = float(os.getenv("MIN_CMD_INTERVAL", "0.12"))