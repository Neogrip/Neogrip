import os
import signal
import sys

#from neogrip import run  

def main() -> int:
    client_id = os.environ["EMOTIV_CLIENT_ID"]
    client_secret = os.environ["EMOTIV_CLIENT_SECRET"]
    profile = os.environ.get("PROFILE_NAME", "")
    port = int(os.environ.get("LOCALHOST_PORT", "6868"))

    return None #run(client_id, client_secret, profile, port)

if __name__ == "__main__":
    raise SystemExit(main())