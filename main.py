# server_raspberry.py
import asyncio
import json
import os
import time
from dataclasses import dataclass
from typing import Dict, Optional


# ---------------- Config moteurs (repris de config.py) ----------------
@dataclass(frozen=True)
class MotorConfig:
    channel: int
    stop_us: int
    open_us: int
    close_us: int
    brake_on_stop_from_open: bool = True
    brake_us: int = 1000
    brake_time_s: float = 0.10
    max_open_angle_deg: float = 90.0
    min_open_angle_deg: float = 0.0
    timer_of_execution: float = 0.5  # secondes pour un mouvement complet open/close


PCA_FREQUENCY_HZ = int(os.getenv("PCA_FREQUENCY_HZ", "330"))

# MOTORS: Dict[str, MotorConfig] = {
#     "thumb":  MotorConfig(channel=0,  stop_us=2000, open_us=3000, close_us=1000),
#     "index":  MotorConfig(channel=3,  stop_us=2000, open_us=3000, close_us=1000),
#     "middle": MotorConfig(channel=7,  stop_us=2000, open_us=3000, close_us=1000),
#     "ring":   MotorConfig(channel=11, stop_us=2000, open_us=3000, close_us=1000),
#     "pinky":  MotorConfig(channel=15, stop_us=2000, open_us=3000, close_us=1000),
# }
MOTORS: Dict[str, MotorConfig] = {
    "thumb":  MotorConfig(channel=0,  stop_us=2000, open_us=2142, close_us=1700),
    "index":  MotorConfig(channel=3,  stop_us=2000, open_us=2142, close_us=1700),
    "middle": MotorConfig(channel=7,  stop_us=2000, open_us=2142, close_us=1700),
    "ring":   MotorConfig(channel=11, stop_us=2000, open_us=2142, close_us=1700),
    "pinky":  MotorConfig(channel=15, stop_us=2000, open_us=2142, close_us=1700),
}
FINGERS = list(MOTORS.keys())
SINGLE_FINGER_MODE = os.getenv("SINGLE_FINGER_MODE", "1") == "1"  # "1" => un seul doigt
ACTIVE_FINGER = os.getenv("ACTIVE_FINGER", "index")               # thumb/index/middle/ring/pinky

POW_ON = float(os.getenv("EMOTIV_POW_ON", "0.35"))
POW_OFF = float(os.getenv("EMOTIV_POW_OFF", "0.25"))
MIN_COMMAND_INTERVAL_S = float(os.getenv("MIN_CMD_INTERVAL", "0.12"))


# ---------------- Backend PCA9685 (repris de servo_backend.py) ----------------
def us_to_duty(pulse_us: int, freq_hz: int) -> int:
    period_us = 1_000_000.0 / float(freq_hz)
    return int(round((pulse_us / period_us) * 65535))


class PCA9685Backend:
    def __init__(self, frequency_hz: int):
        import busio
        from board import SCL, SDA
        from adafruit_pca9685 import PCA9685

        self.frequency_hz = frequency_hz
        i2c = busio.I2C(SCL, SDA)
        self.pca = PCA9685(i2c)
        self.pca.frequency = frequency_hz

    def set_us(self, channel: int, pulse_us: int) -> None:
        self.pca.channels[channel].duty_cycle = us_to_duty(pulse_us, self.frequency_hz)

    def deinit(self) -> None:
        self.pca.deinit()


# ---------------- Servo motor + contrôleur main (repris de servo_motor.py + hand_controller.py) ----------------
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
        if self.cfg.brake_on_stop_from_open and self.state == "open":
            self.backend.set_us(self.cfg.channel, self.cfg.brake_us)
            await asyncio.sleep(self.cfg.brake_time_s)

        self.backend.set_us(self.cfg.channel, self.cfg.stop_us)
        self.state = "stop"

    def hard_stop(self) -> None:
        # stop immédiat, sans frein ni sleep
        self.backend.set_us(self.cfg.channel, self.cfg.stop_us)
        self.state = "stop"

class HandController:
    def __init__(self, backend, pow_on: float, pow_off: float, min_interval_s: float):
        self.backend = backend
        self.pow_on = pow_on
        self.pow_off = pow_off
        self.min_interval_s = min_interval_s
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

    def hard_stop_all(self) -> None:
        for m in self.motors.values():
            m.hard_stop()
        self._hand_state = "stop"
        self._last_cmd_t = time.time()

    async def _apply_one(self, finger: str, action: str) -> None:
        m = self.motors[finger]
        if action == "open":
            await m.open()
        elif action == "close":
            await m.close()
        else:
            await m.stop()

    async def _apply_action(self, action: str) -> None:
        """
        Applique l'action soit à toute la main (comportement historique),
        soit à un seul doigt (mode single-finger), sans supprimer la logique main entière.
        """
        if SINGLE_FINGER_MODE:
            # Optionnel mais conseillé: garantir que les autres sont stoppés
            # await asyncio.gather(*(m.stop() for name, m in self.motors.items() if name != ACTIVE_FINGER))
            await self._apply_one(ACTIVE_FINGER, action)
        else:
            await self._apply_all(action)


    async def apply_com(self, act: str, pow_: float) -> Optional[str]:
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

        await self._apply_action(target)
        self._hand_state = target
        self._last_cmd_t = now
        return target


# ---------------- TCP server ----------------
async def handle_client(reader, writer, hand: HandController, shutdown_event: asyncio.Event):
    addr = writer.get_extra_info("peername")
    print(f"[SERVER] Client connecté: {addr}")

    try:
        while True:
            line = await reader.readline()
            if not line:
                break
            try:
                msg = json.loads(line.decode("utf-8", errors="replace").strip())
            except json.JSONDecodeError:
                continue

            # --- KILLSWITCH
            if str(msg.get("act", "")).upper() == "KILLSWITCH":
                print("[SERVER] KILLSWITCH reçu -> HARD STOP + shutdown")
                hand.hard_stop_all()
                shutdown_event.set()
                break

            if msg.get("type") != "com":
                continue

            act = str(msg.get("act", ""))
            pow_ = float(msg.get("pow", 0.0))

            new_state = await hand.apply_com(act, pow_)
            if new_state:
                print(f"[SERVER] com act={act} pow={pow_:.3f} => hand={new_state}")

    finally:
        print(f"[SERVER] Client déconnecté: {addr}")
        writer.close()
        await writer.wait_closed()


async def main():
    host = os.getenv("NEOGRIP_BIND", "0.0.0.0")
    port = int(os.getenv("NEOGRIP_SERVER_PORT", "8764"))

    backend = PCA9685Backend(PCA_FREQUENCY_HZ)
    hand = HandController(backend, POW_ON, POW_OFF, MIN_COMMAND_INTERVAL_S)

    shutdown_event = asyncio.Event()

    server = await asyncio.start_server(
        lambda r, w: handle_client(r, w, hand, shutdown_event),
        host, port
    )

    addrs = ", ".join(str(s.getsockname()) for s in server.sockets or [])
    print(f"[SERVER] Listen on {addrs}")
    print("[SERVER] Mapping: push=open, pull=close, sinon stop (hystérésis).")

    try:
        async with server:
            await shutdown_event.wait()
    finally:
        server.close()
        await server.wait_closed()
        try:
            await hand.stop_all()
        finally:
            backend.deinit()



if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass