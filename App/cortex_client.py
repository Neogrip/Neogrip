import json
import ssl
from typing import Any, Dict, Optional, AsyncIterator, Tuple

import websockets


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
        rid = await self._send("authorize", {
            "clientId": self.client_id,
            "clientSecret": self.client_secret,
            "debit": int(self.debit),
            "license": ""
        })
        resp = await self._recv_until_id(rid)
        self.token = resp["result"]["cortexToken"]

    async def query_headset(self) -> None:
        rid = await self._send("queryHeadsets", {})
        resp = await self._recv_until_id(rid)
        hs = resp.get("result", [])
        if not hs:
            raise RuntimeError("Aucun headset détecté.")
        self.headset_id = hs[0]["id"]

    async def load_profile(self, profile_name: str) -> None:
        # getCurrentProfile
        rid = await self._send("getCurrentProfile", {"cortexToken": self.token, "headset": self.headset_id})
        cur = (await self._recv_until_id(rid)).get("result", {})
        cur_name = cur.get("name")
        loaded_by_this_app = cur.get("loadedByThisApp")

        if cur_name and cur_name != profile_name:
            if not loaded_by_this_app:
                raise RuntimeError(
                    f"Profil '{cur_name}' déjà chargé par une autre application. "
                    "Fermez l’autre app ou déchargez depuis elle."
                )
            rid = await self._send("setupProfile", {
                "cortexToken": self.token, "headset": self.headset_id,
                "profile": "", "status": "unload"
            })
            await self._recv_until_id(rid)

        if cur_name != profile_name:
            rid = await self._send("setupProfile", {
                "cortexToken": self.token, "headset": self.headset_id,
                "profile": profile_name, "status": "load"
            })
            await self._recv_until_id(rid)

    async def open_and_activate_session(self) -> None:
        rid = await self._send("createSession", {
            "cortexToken": self.token, "headset": self.headset_id, "status": "open"
        })
        resp = await self._recv_until_id(rid)
        self.session_id = resp["result"]["id"]

        rid = await self._send("updateSession", {
            "cortexToken": self.token, "session": self.session_id, "status": "active"
        })
        await self._recv_until_id(rid)

    async def subscribe_com(self) -> None:
        rid = await self._send("subscribe", {
            "cortexToken": self.token,
            "session": self.session_id,
            "streams": ["com"]
        })
        await self._recv_until_id(rid)

    async def com_stream(self) -> AsyncIterator[Tuple[str, float]]:
        """
        Messages attendus:
          {"com": ["push", 0.376], "sid": "...", "time": ...}
        """
        while True:
            msg = json.loads(await self.ws.recv())
            if "com" not in msg:
                continue
            com = msg["com"]
            if isinstance(com, list) and len(com) >= 2:
                yield str(com[0]), float(com[1])