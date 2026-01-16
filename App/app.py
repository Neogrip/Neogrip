import asyncio

from config import (
    CORTEX_URL, CLIENT_ID, CLIENT_SECRET, DEBIT,
    LOAD_PROFILE, PROFILE_NAME,
    PCA_FREQUENCY_HZ,
    POW_ON, POW_OFF, MIN_COMMAND_INTERVAL_S
)
from cortex_client import CortexClient
from servo_backend import PCA9685Backend, make_backend
from hand_controller import HandController


async def run():
    cortex = CortexClient(CORTEX_URL, CLIENT_ID, CLIENT_SECRET, debit=DEBIT)
    #backend = PCA9685Backend(PCA_FREQUENCY_HZ)
    backend = make_backend(PCA_FREQUENCY_HZ)
    hand = HandController(backend, POW_ON, POW_OFF, MIN_COMMAND_INTERVAL_S)

    await cortex.connect()
    try:
        await cortex.request_access()
        await cortex.authorize()
        await cortex.query_headset()

        if LOAD_PROFILE:
            await cortex.load_profile(PROFILE_NAME)

        await cortex.open_and_activate_session()
        await cortex.subscribe_com()

        print("OK: Cortex COM -> main. push=open, pull=close, sinon stop.")

        async for act, pow_ in cortex.com_stream():
            new_state = await hand.apply_com(act, pow_)
            if new_state:
                print(f"com act={act} pow={pow_:.3f} => hand={new_state}")

    finally:
        try:
            await hand.stop_all()
        finally:
            backend.deinit()
            await cortex.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass