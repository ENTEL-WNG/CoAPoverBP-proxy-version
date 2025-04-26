import asyncio
import sys
import os
import random
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'aiocoap', 'src'))
sys.path.insert(0, project_root)
from aiocoap import *

COAP_PROXY_URI = "coap://localhost:5685" 

async def main():
    context = await Context.create_client_context()

    pending_tasks = []

    while True:
        print("\nOptions:")
        print(" 1 - PUT temperature")
        print(" 2 - FLUSH and wait for responses")
        print(" 3 - EXIT")
        choice = input("Select: ")

        if choice == "1":
            temperature = round(random.uniform(15.0, 30.0), 2)
            print(f"[Client] Queueing PUT /temperature: {temperature}")
            request = Message(
                mtype=NON,
                code=PUT,
                uri=f"{COAP_PROXY_URI}/temperature",
                payload=str(temperature).encode("utf-8")
            )
        elif choice == "2":
            print("Waiting for all queued responses...")

            responses = await asyncio.gather(*pending_tasks, return_exceptions=True)

            for idx, resp in enumerate(responses):
                if isinstance(resp, Exception):
                    print(f"[Client] Request {idx} failed: {resp}")
                else:
                    print(f"[Client] Response {idx}: {resp.code}")
                    print(f"Payload: {resp.payload.decode('utf-8')}")
                    print(f"MID: {resp.mid}")

            pending_tasks.clear()
            continue 
        elif choice == "3":
            print("Exiting.")
            break
        else:
            print("Invalid choice.")
            continue

        try:
            task = context.request(request).response
            pending_tasks.append(task)
        except Exception as e:
            print(f"[Client] Request setup failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
