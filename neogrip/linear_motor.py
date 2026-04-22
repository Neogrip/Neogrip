from dataclasses import dataclass

from .config import LinearMotorConfig

@dataclass
class LinearMotor:
    name: str
    cfg: LinearMotorConfig
    backend: any
    state: str = "stop"

    # Dans e cadre de nos moteurs: Une extension correspond à la fermeture des doigts
    async def close(self):
        self.backend.set_digital(self.cfg.in1, True)
        self.backend.set_digital(self.cfg.in2, False)
        self.state = "close"

    async def open(self):
        self.backend.set_digital(self.cfg.in1, False)
        self.backend.set_digital(self.cfg.in2, True)
        self.state = "open"

    async def stop(self):
        self.backend.set_digital(self.cfg.in1, False)
        self.backend.set_digital(self.cfg.in2, False)
        self.state = "stop"