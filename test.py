import asyncio, json, ssl, websockets

PI_IP = "127.0.0.1"                       # IP du Raspberry Pi
URL = f"wss://{PI_IP}:6868"

async def send(ws, payload):
    await ws.send(json.dumps(payload))
    resp = json.loads(await ws.recv())
    # Affiche la réponse pour debug
    print("RPC", payload.get("method"), "→", json.dumps(resp, ensure_ascii=False))
    # Si erreur, lève une exception claire
    if "error" in resp:
        code = resp["error"].get("code")
        msg = resp["error"].get("message")
        raise RuntimeError(f"{payload.get('method')} failed: [{code}] {msg}")
    return resp

async def cortex():
    ssl_ctx = ssl._create_unverified_context()
    async with websockets.connect(URL, ssl=ssl_ctx) as ws:
        # 1) authorize
        auth = await send(ws, {
            "jsonrpc": "2.0","method": "authorize","id": 1,
            "params": {"clientId": CLIENT_ID, "clientSecret": CLIENT_SECRET}
        })
        token = auth["result"]["cortexToken"]

        # 2) Lister les casques visibles par Cortex
        headsets = await send(ws, {
            "jsonrpc":"2.0","method":"queryHeadsets","id":2,"params":{}
        })
        hs = headsets["result"]
        if not hs:
            raise RuntimeError("Aucun headset détecté par Cortex. Branche un casque ou active un 'Virtual Brainwear' connecté au même Cortex.")

        # Option : choisir le premier 'connected'
        headset_id = next((h["id"] for h in hs if h.get("status") == "connected"), hs[0]["id"])

        # 3) createSession (active) avec un headset explicite
        sess = await send(ws, {
            "jsonrpc":"2.0","method":"createSession","id":3,
            "params":{"cortexToken": token, "status":"active", "headset": headset_id}
        })
        session_id = sess["result"]["id"]

        # 4) subscribe
        await send(ws, {
            "jsonrpc":"2.0","method":"subscribe","id":4,
            "params":{"cortexToken": token, "session": session_id, "streams":["eeg","dev"]}
        })

        # 5) lire quelques messages (brut)
        for _ in range(10):
            print(await ws.recv())

asyncio.run(cortex())
