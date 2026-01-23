# client_windows.py
import asyncio
import json
import os
import ssl
import time
from typing import Optional, Tuple, AsyncIterator, Any, Dict
import msvcrt
import websockets
from pynput import keyboard
import threading


# ---------------- Cortex Client (repris / simplifié depuis cortex_client.py) ----------------
class CortexClient:
    def __init__(self, url: str, client_id: str, client_secret: str, debit: int = 10):
        self.url = url
        self.client_id = client_id
        self.client_secret = client_secret
        self.debit = debit

        self.ws = None
        self._msg_id = 0
        self.token: Optional[str] = None
        self.headset_id: Optional[str] = None
        self.session_id: Optional[str] = None

    def _next_id(self) -> int:
        self._msg_id += 1
        return self._msg_id

    async def _send(self, method: str, params: Dict[str, Any]) -> int:
        rid = self._next_id()
        await self.ws.send(json.dumps({"jsonrpc": "2.0", "id": rid, "method": method, "params": params}))
        return rid

    async def _recv_until_id(self, rid: int) -> Dict[str, Any]:
        while True:
            msg = json.loads(await self.ws.recv())
            if msg.get("id") == rid:
                if "error" in msg:
                    raise RuntimeError(f"Cortex error for id={rid}: {msg['error']}")
                return msg

    async def connect(self) -> None:
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        self.ws = await websockets.connect(self.url, ssl=ssl_ctx)

    async def close(self) -> None:
        if self.ws:
            await self.ws.close()
            self.ws = None

    async def request_access(self) -> None:
        rid = await self._send("requestAccess", {"clientId": self.client_id, "clientSecret": self.client_secret})
        resp = await self._recv_until_id(rid)
        if not resp.get("result", {}).get("accessGranted", False):
            raise RuntimeError("Access refusé: autorisez l’app côté EMOTIV (requestAccess).")

    async def authorize(self) -> None:
        rid = await self._send(
            "authorize",
            {"clientId": self.client_id, "clientSecret": self.client_secret, "debit": int(self.debit), "license": ""},
        )
        resp = await self._recv_until_id(rid)
        self.token = resp["result"]["cortexToken"]

    async def control_device(self, command: str, headset_id: Optional[str] = None) -> None:
        params = {"command": command}
        if headset_id is not None:
            params["headset"] = headset_id
        rid = await self._send("controlDevice", params)
        await self._recv_until_id(rid)

    async def load_profile(self, profile_name: str) -> None:
        if not self.token:
            raise RuntimeError("Token Cortex manquant.")
        if not self.headset_id:
            raise RuntimeError("Headset id manquant.")

        print(f"[DEBUG] token={self.token[:8]}... headset_id={self.headset_id!r} profile={profile_name!r}")

        rid = await self._send("getCurrentProfile", {"cortexToken": self.token, "headset": self.headset_id})
        cur = (await self._recv_until_id(rid)).get("result", {})
        cur_name = cur.get("name")
        loaded_by_this_app = cur.get("loadedByThisApp")

        if cur_name and cur_name != profile_name:
            if not loaded_by_this_app:
                raise RuntimeError(
                    f"Profil '{cur_name}' déjà chargé par une autre application."
                )
            rid = await self._send(
                "setupProfile",
                {"cortexToken": self.token, "headset": self.headset_id, "profile": "", "status": "unload"},
            )
            await self._recv_until_id(rid)

        if cur_name != profile_name:
            rid = await self._send(
                "setupProfile",
                {"cortexToken": self.token, "headset": self.headset_id, "profile": profile_name, "status": "load"},
            )
            await self._recv_until_id(rid)


    async def query_headset(self) -> None:
        rid = await self._send("queryHeadsets", {})
        resp = await self._recv_until_id(rid)
        hs = resp.get("result", [])
        print("[DEBUG] queryHeadsets =", hs)

        if not hs:
            raise RuntimeError("Aucun headset détecté.")

        # Priorité au virtuel connecté
        for h in hs:
            if h.get("isVirtual") and h.get("status") == "connected":
                self.headset_id = h["id"]
                print(f"[DEBUG] Selected virtual headset: {h.get('customName','')} ({self.headset_id})")
                return

        # Fallback: premier connecté
        for h in hs:
            if h.get("status") == "connected":
                self.headset_id = h["id"]
                print(f"[DEBUG] Selected headset: {h.get('customName','')} ({self.headset_id})")
                return

        raise RuntimeError("Headsets détectés mais aucun n'est 'connected'.")


    async def open_and_activate_session(self) -> None:
        rid = await self._send("createSession", {"cortexToken": self.token, "headset": self.headset_id, "status": "open"})
        resp = await self._recv_until_id(rid)
        self.session_id = resp["result"]["id"]

        rid = await self._send(
            "updateSession", {"cortexToken": self.token, "session": self.session_id, "status": "active"}
        )
        await self._recv_until_id(rid)

    async def subscribe_com(self) -> None:
        rid = await self._send(
            "subscribe", {"cortexToken": self.token, "session": self.session_id, "streams": ["com"]}
        )
        await self._recv_until_id(rid)

    async def com_stream(self) -> AsyncIterator[Tuple[str, float]]:
        while True:
            msg = json.loads(await self.ws.recv())
            if "com" not in msg:
                continue
            com = msg["com"]
            if isinstance(com, list) and len(com) >= 2:
                yield str(com[0]), float(com[1])

    async def shutdown(self) -> None:
        # Ferme la session et libère le casque proprement, puis ferme la ws.
        try:
            if self.ws and self.token and self.session_id:
                rid = await self._send("updateSession", {
                    "cortexToken": self.token,
                    "session": self.session_id,
                    "status": "close"
                })
                await self._recv_until_id(rid)
        except Exception as e:
            print("[WARN] updateSession close failed:", e)

        try:
            if self.ws and self.token:
                # release sans params dans beaucoup d'exemples; si ton API demande headset,
                # tu peux passer {"cortexToken": self.token, "headset": self.headset_id}
                rid = await self._send("release", {})
                await self._recv_until_id(rid)
        except Exception as e:
            print("[WARN] release failed:", e)

        await self.close()


# ---------------- TCP sender (line-delimited JSON) ----------------
async def send_loop(writer: asyncio.StreamWriter, act: str, pow_: float) -> None:
    payload = {"type": "com", "act": act, "pow": pow_, "ts": time.time()}
    writer.write((json.dumps(payload) + "\n").encode("utf-8"))
    await writer.drain()

def start_global_killswitch_listener(
    loop: asyncio.AbstractEventLoop,
    stop_event: asyncio.Event,
    trigger_keys=("k",),      # touches simples
    trigger_esc=True,         # ESC
    trigger_ctrl_shift_k=True # hotkey Ctrl+Shift+K
) -> keyboard.Listener:
    """
    Démarre un listener clavier global (même si une autre app a le focus).
    Quand le killswitch est détecté => stop_event.set() thread-safe.
    """

    # Pour le combo Ctrl+Shift+K
    pressed = set()

    def request_stop():
        if not stop_event.is_set():
            loop.call_soon_threadsafe(stop_event.set)

    def on_press(key):
        # Gestion combo
        try:
            if key in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
                pressed.add("ctrl")
            elif key in (keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r):
                pressed.add("shift")
            elif hasattr(key, "char") and key.char:
                pressed.add(key.char.lower())
        except Exception:
            pass

        # ESC
        if trigger_esc and key == keyboard.Key.esc:
            request_stop()
            return False

        # touche simple (ex: 'k')
        # if hasattr(key, "char") and key.char:
        #     if key.char.lower() in trigger_keys:
        #         request_stop()
        #         return False

        # combo Ctrl+Shift+K
        if trigger_ctrl_shift_k and {"ctrl", "shift", "k"}.issubset(pressed):
            request_stop()
            return False

    def on_release(key):
        try:
            if key in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
                pressed.discard("ctrl")
            elif key in (keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r):
                pressed.discard("shift")
            elif hasattr(key, "char") and key.char:
                pressed.discard(key.char.lower())
        except Exception:
            pass

    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.start()  # thread interne
    return listener


async def killswitch_sender_loop(
    writer: asyncio.StreamWriter,
    stop_event: asyncio.Event,
) -> None:
    """
    Attend stop_event (déclenché par le listener global), puis envoie KILLSWITCH une fois.
    """
    print("[KEY] KILLSWITCH global actif (ESC / k / Ctrl+Shift+K).")
    await stop_event.wait()
    try:
        await send_loop(writer, "KILLSWITCH", 1.0)
        print("[KEY] KILLSWITCH envoyé.")
    except Exception as e:
        print("[KEY] Erreur envoi KILLSWITCH:", e)


async def com_to_raspberry_loop(
    cortex: CortexClient,
    writer: asyncio.StreamWriter,
    stop_event: asyncio.Event,
) -> None:
    async for act, pow_ in cortex.com_stream():
        if stop_event.is_set():
            return
        await send_loop(writer, act, pow_)



async def main():
    RPI_HOST = os.getenv("NEOGRIP_HOST", "192.168.1.50")
    RPI_PORT = int(os.getenv("NEOGRIP_PORT", "8764"))

    cortex_url = os.getenv("CORTEX_URL", "wss://localhost:6868")
    client_id = os.getenv("EMOTIV_CLIENT_ID", "dikQvTTxwaSSHBL4HhFpjbFhNW0LDVJ64A9I2TmY")
    client_secret = os.getenv("EMOTIV_CLIENT_SECRET", "jqiDiUlE1dycz9LmaeiThEWbTNhNwsLy8VtnLkeUqRL6S9iIuREhpV76ZCWk0fhr7w7pDOIIzfKcqWd5Znb0y4MTkLJyn0H7f6DEY8EarRGp7MJw3x7JJi1GauNLLM1t")
    debit = int(os.getenv("EMOTIV_DEBIT", "10"))

    load_profile = os.getenv("EMOTIV_LOAD_PROFILE", "1") == "0"
    profile = os.getenv("EMOTIV_PROFILE", "popoche")

    stop_event = asyncio.Event()

    cortex = CortexClient(cortex_url, client_id, client_secret, debit=10)

    writer = None
    try:
        # Connexion TCP vers Raspberry
        print(f"[CLIENT] Connexion TCP vers {RPI_HOST}:{RPI_PORT} ...")
        reader, writer = await asyncio.open_connection(RPI_HOST, RPI_PORT)
        print(f"[CLIENT] Connecté au Raspberry {RPI_HOST}:{RPI_PORT}")

        # Cortex setup
        await cortex.connect()
        await cortex.request_access()
        await cortex.authorize()
        await cortex.query_headset()

        # (optionnel) connect headset si nécessaire
        # await cortex.control_device("connect", cortex.headset_id)

        await cortex.open_and_activate_session()
        if load_profile:
            await cortex.load_profile(profile)
        await cortex.subscribe_com()

        loop = asyncio.get_running_loop()

        # event local pour arrêter (déjà chez toi)
        stop_event = asyncio.Event()

        # démarre le listener global clavier
        listener = start_global_killswitch_listener(loop, stop_event)

        # tasks asyncio
        t_com = asyncio.create_task(com_to_raspberry_loop(cortex, writer, stop_event))
        t_kill = asyncio.create_task(killswitch_sender_loop(writer, stop_event))

        done, pending = await asyncio.wait({t_com, t_kill}, return_when=asyncio.FIRST_COMPLETED)

        stop_event.set()
        for t in pending:
            t.cancel()
        await asyncio.gather(*pending, return_exceptions=True)

        # stop le listener (propre)
        try:
            listener.stop()
        except Exception:
            pass

        # Stop les autres
        stop_event.set()
        for t in pending:
            t.cancel()
        await asyncio.gather(*pending, return_exceptions=True)

    finally:
        # Fermer TCP
        if writer:
            writer.close()
            await writer.wait_closed()

        # Arrêt propre Cortex (évite headset busy)
        await cortex.shutdown()

        print("[MAIN] Terminé.")


# async def main():
#     # ---- Emotiv (comme config.py) ----
#     cortex_url = os.getenv("CORTEX_URL", "wss://localhost:6868")
#     client_id = os.getenv("EMOTIV_CLIENT_ID", "dikQvTTxwaSSHBL4HhFpjbFhNW0LDVJ64A9I2TmY")
#     client_secret = os.getenv("EMOTIV_CLIENT_SECRET", "jqiDiUlE1dycz9LmaeiThEWbTNhNwsLy8VtnLkeUqRL6S9iIuREhpV76ZCWk0fhr7w7pDOIIzfKcqWd5Znb0y4MTkLJyn0H7f6DEY8EarRGp7MJw3x7JJi1GauNLLM1t")
#     debit = int(os.getenv("EMOTIV_DEBIT", "10"))

#     load_profile = os.getenv("EMOTIV_LOAD_PROFILE", "1") == "0"
#     profile_name = os.getenv("EMOTIV_PROFILE", "popoche")

#     # ---- Raspberry server ----
#     server_host = os.getenv("NEOGRIP_SERVER_HOST", "192.168.1.50")
#     server_port = int(os.getenv("NEOGRIP_SERVER_PORT", "8765"))

#     if not client_id or not client_secret:
#         raise RuntimeError("EMOTIV_CLIENT_ID / EMOTIV_CLIENT_SECRET manquants (variables d'env).")

#     print(f"[CLIENT] Connexion TCP vers {server_host}:{server_port} ...")
#     reader, writer = await asyncio.open_connection(server_host, server_port)
#     print("[CLIENT] TCP OK.")

#     cortex = CortexClient(cortex_url, client_id, client_secret, debit=debit)
#     await cortex.connect()
#     try:
#         await cortex.request_access()
#         await cortex.authorize()
#         await cortex.query_headset()
#         if load_profile:
#             await cortex.load_profile(profile_name)
#         await cortex.open_and_activate_session()
#         await cortex.subscribe_com()

#         print("[CLIENT] OK: Cortex com -> envoi vers Raspberry (push/pull + pow).")
#         async for act, pow_ in cortex.com_stream():
#             await send_loop(writer, act, pow_)
#     finally:
#         try:
#             writer.close()
#             await writer.wait_closed()
#         finally:
#             await cortex.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
