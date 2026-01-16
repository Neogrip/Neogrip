import asyncio
import time
from typing import Optional

from config import MOTORS, FINGERS


class HandController:
    def __init__(self, backend, pow_on: float, pow_off: float, min_interval_s: float):
        self.backend = backend
        self.pow_on = pow_on
        self.pow_off = pow_off
        self.min_interval_s = min_interval_s

        from servo_motor import ServoMotor
        self.motors = {name: ServoMotor(name, cfg, backend) for name, cfg in MOTORS.items()}

        self._hand_state = "stop"
        self._last_cmd_t = 0.0

    async def _apply_all(self, action: str) -> None:
        if action == "open":
            await asyncio.gather(*(self.motors[f].open() for f in FINGERS))
        elif action == "close":
            await asyncio.gather(*(self.motors[f].close() for f in FINGERS))
        else:
            await asyncio.gather(*(self.motors[f].stop() for f in FINGERS))

    async def stop_all(self) -> None:
        await self._apply_all("stop")

    async def apply_com(self, act: str, pow_: float) -> Optional[str]:
        """
        Mapping demandé:
          push -> open (main)
          pull -> close (main)
          sinon -> stop (si pow bas)
        """
        now = time.time()
        if now - self._last_cmd_t < self.min_interval_s:
            return None

        target = self._hand_state

        if act == "push" and pow_ >= self.pow_on:
            target = "open"
        elif act == "pull" and pow_ >= self.pow_on:
            target = "close"
        else:
            if pow_ <= self.pow_off:
                target = "stop"

        if target == self._hand_state:
            return None

        await self._apply_all(target)
        self._hand_state = target
        self._last_cmd_t = now
        return target