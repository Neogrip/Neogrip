import asyncio
from dataclasses import dataclass

from config import MotorConfig


@dataclass
class ServoMotor:
    name: str
    cfg: MotorConfig
    backend: any
    state: str = "stop"  # "open" | "close" | "stop"

    async def open(self) -> None:
        self.backend.set_us(self.cfg.channel, self.cfg.open_us)
        self.state = "open"

    async def close(self) -> None:
        self.backend.set_us(self.cfg.channel, self.cfg.close_us)
        self.state = "close"

    async def stop(self) -> None:
        # Votre “anti-clockwise bugfix”: frein bref si stop après open
        if self.cfg.brake_on_stop_from_open and self.state == "open":
            self.backend.set_us(self.cfg.channel, self.cfg.brake_us)
            await asyncio.sleep(self.cfg.brake_time_s)

        self.backend.set_us(self.cfg.channel, self.cfg.stop_us)
        self.state = "stop"