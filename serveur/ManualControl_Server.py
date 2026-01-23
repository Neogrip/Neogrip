import asyncio
import time
import websockets
import busio
from board import SCL, SDA
from adafruit_pca9685 import PCA9685

DEV_ENV = False

# Conversion µs → duty_cycle pour le PCA9685
def us_to_duty(pulse_us, freq_hz):
    period_us = 1_000_000.0 / freq_hz
    return int(round((pulse_us / period_us) * 65535))

# --- CONFIG SERVO ---
FREQ = 330        # fréquence du signal PWM
STOP_US = 2000 # arrêt
OPEN_US = 2350 # tourne anti-horaire: pb d'élan
CLOSE_US = 1500 # tourne horraire


# --- CONVERSION µs -> duty_cycle ---
STOP = us_to_duty(STOP_US, FREQ)
OPEN = us_to_duty(OPEN_US, FREQ)
CLOSE = us_to_duty(CLOSE_US, FREQ)

# --- INITIALISATION I2C / PCA9685 ---
if DEV_ENV == False:
    i2c = busio.I2C(SCL, SDA)
    pca = PCA9685(i2c)
    pca.frequency = FREQ

    # --- SERVOS / CANAUX ---
    servos = {
        "pinky": pca.channels[15],
        "ring": pca.channels[11],
        "middle": pca.channels[7],
        "index": pca.channels[3],
        "thumb": pca.channels[0]
    }

# --- État des moteurs ---
if DEV_ENV == False:
    etat_moteurs = {m: "stop" for m in servos}
else:
    etat_moteurs = {"pinky": "stop", "ring": "stop", "middle": "stop", "index": "stop", "thumb": "stop"}

# --- Fonctions moteurs ---
def moteur_start(moteur, sens):
    if DEV_ENV == False:
        servo = servos[moteur]
        if sens == "open":
            servo.duty_cycle = OPEN
        else:
            servo.duty_cycle = CLOSE
    etat_moteurs[moteur] = sens
    print(f"[{moteur}] -> {sens}")

def moteur_stop(moteur):
    if DEV_ENV == False:
        if etat_moteurs[moteur] == "open":
            servos[moteur].duty_cycle = CLOSE
            time.sleep(0.03)
            servos[moteur].duty_cycle = STOP
        else:
            servos[moteur].duty_cycle = STOP
    etat_moteurs[moteur] = "stop"
    print(f"[{moteur}] -> stop")

# --- Serveur WebSocket ---
async def controle(websocket, path = "/"):
    rotationActuelle = None
    async for message in websocket:
        try:
            moteur, action = message.split(":")
        except ValueError:
            continue

        if moteur not in servos:
            continue

        if action == "stop":
            moteur_stop(moteur)
        elif action in ["open", "close"]:
            moteur_start(moteur, action)
        else:
            continue

        await websocket.send(f"{moteur}:{etat_moteurs[moteur]}")

# --- Lancement serveur ---
async def main():
    async with websockets.serve(controle, "0.0.0.0", 6789):
        print("Serveur WebSocket démarré sur ws://0.0.0.0:6789")
        await asyncio.Future()  # bloque indéfiniment

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # arrêt propre
        for m in servos:
            servos[m].duty_cycle = STOP
        pca.deinit()
        print("Tous les servos arrêtés.")
