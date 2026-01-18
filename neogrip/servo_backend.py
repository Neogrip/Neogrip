import os
import sys
from dataclasses import dataclass

def us_to_duty(pulse_us: int, freq_hz: int) -> int:
    period_us = 1_000_000.0 / float(freq_hz)
    return int(round((pulse_us / period_us) * 65535))

@dataclass(frozen=True)
class BackendConfig:
    frequency_hz: int

class ServoBackend:
    def set_us(self, channel: int, pulse_us: int) -> None:
        raise NotImplementedError
    def deinit(self) -> None:
        pass

class NullBackend(ServoBackend):
    """
    Backend simulé: ne touche pas au hardware.
    Utile sur Windows / sans PCA9685.
    """
    def __init__(self, cfg: BackendConfig):
        self.cfg = cfg
        self.last = {}  # channel -> pulse_us

    def set_us(self, channel: int, pulse_us: int) -> None:
        self.last[channel] = pulse_us
        print(f"[DEV] ch={channel:02d} pulse={pulse_us}us (freq={self.cfg.frequency_hz}Hz)")

class PCA9685Backend(ServoBackend):
    """
    Backend réel: PCA9685 via I2C.
    Important: imports hardware UNIQUEMENT ici.
    """
    def __init__(self, cfg: BackendConfig):
        import busio
        from board import SCL, SDA
        from adafruit_pca9685 import PCA9685

        self.cfg = cfg
        i2c = busio.I2C(SCL, SDA)
        self.pca = PCA9685(i2c)
        self.pca.frequency = cfg.frequency_hz

    def set_us(self, channel: int, pulse_us: int) -> None:
        self.pca.channels[channel].duty_cycle = us_to_duty(pulse_us, self.cfg.frequency_hz)

    def deinit(self) -> None:
        self.pca.deinit()

def make_backend(frequency_hz: int) -> ServoBackend:
    """
    Sélection automatique:
    - sur Windows => NullBackend
    - si NEOGRIP_DEV=1 => NullBackend
    - sinon => PCA9685Backend
    """
    cfg = BackendConfig(frequency_hz=frequency_hz)

    if os.getenv("NEOGRIP_DEV", "0") == "1":
        return NullBackend(cfg)

    if sys.platform.startswith("win"):
        return NullBackend(cfg)

    return PCA9685Backend(cfg)