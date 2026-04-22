import asyncio
import websockets
import board
import busio
from adafruit_pca9685 import PCA9685

# --- PCA9685 ---
i2c = busio.I2C(board.SCL, board.SDA)
pca = PCA9685(i2c)
pca.frequency = 1000

IN1 = 0
IN2 = 1

# def set_pin(ch, value):
#     pca.channels[ch].duty_cycle = 65535 if value else 0
def set_pin(ch, value):
    if value:
        pca.channels[ch].duty_cycle = 0xFFFF
    else:
        pca.channels[ch].duty_cycle = 0x0000

def forward():
    set_pin(IN1, 1)
    set_pin(IN2, 0)

def backward():
    set_pin(IN1, 0)
    set_pin(IN2, 1)

def stop():
    set_pin(IN1, 0)
    set_pin(IN2, 0)

async def handler(websocket):
    print("Client connecté")

    async for message in websocket:
        print("Reçu:", message)

        if message == "UP":
            forward()
        elif message == "DOWN":
            backward()
        elif message == "STOP":
            stop()

async def main():
    async with websockets.serve(handler, "0.0.0.0", 8765):
        print("Serveur WebSocket prêt sur port 8765")
        await asyncio.Future()

asyncio.run(main())
# forward()
