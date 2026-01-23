import asyncio
import websockets
from pynput import keyboard

# --- Configuration ---
#SERVER = "ws://192.168.137.87:6789"
SERVER = "ws://192.168.1.50:6789"

# --- Mapping touches → commandes moteur ---
TOUCHES = {
    'p': 'pinky:open',
    'm': 'pinky:close',
    'o': 'ring:open',
    'l': 'ring:close',
    'i': 'middle:open',
    'k': 'middle:close',
    'u': 'index:open',
    'j': 'index:close',
    'v': 'thumb:open',
    'b': 'thumb:close'
}

# --- État des touches maintenues ---
touches_actives = set()
# --- État des moteurs pour éviter d'envoyer des messages inutiles ---
etat_moteurs = {}

async def envoyer_commande(websocket, message):
    await websocket.send(message)
    response = await websocket.recv()
    print(f"Réponse serveur: {response}")

def on_press(key):
    try:
        if key.char in TOUCHES:
            touches_actives.add(key.char)
    except AttributeError:
        pass

def on_release(key):
    try:
        if key.char in TOUCHES:
            touches_actives.discard(key.char)
    except AttributeError:
        pass

async def client():
    async with websockets.connect(SERVER) as websocket:
        print("Connecté au serveur WebSocket")
        try:
            while True:
                # Envoi des commandes pour toutes les touches maintenues
                for touche in list(touches_actives):
                    commande = TOUCHES[touche]
                    moteur, action = commande.split(":")
                    if etat_moteurs.get(moteur) != action:
                        await envoyer_commande(websocket, commande)
                        etat_moteurs[moteur] = action

                # Vérifier les moteurs dont la touche n'est plus maintenue
                for moteur, action in list(etat_moteurs.items()):
                    # trouver la touche associée à ce moteur/action
                    touche_assoc = [k for k,v in TOUCHES.items() if v == f"{moteur}:{action}"]
                    if touche_assoc and touche_assoc[0] not in touches_actives and action != "stop":
                        await envoyer_commande(websocket, f"{moteur}:stop")
                        etat_moteurs[moteur] = "stop"

                await asyncio.sleep(0.05)
        except KeyboardInterrupt:
            print("\nClient arrêté")

if __name__ == "__main__":
    # Lancement du listener clavieruuuuuuujjjjjjjjikkkiiikkpppmmoollllllllloooooolllllllliikkkkkkkkkkkkkkkkkkiiiiiijuuuuujjjjjjikkkkkiiiikkkkkkkoooooollllllpmmm
    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.start()  # non bloquant

    # Lancement du client WebSocket
    try:
        asyncio.run(client())
    except KeyboardInterrupt:
        print("\nArrêt du client")
