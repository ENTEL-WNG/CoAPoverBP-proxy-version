import asyncio
from aiocoap import *
import random

COAP_PROXY_URI = "coap://localhost:5685" # Connects to Node A's proxy

async def main():
    context = await Context.create_client_context()

    while True:
        print("\nOptions:")
        print(" 1 - PUT temperature")
        print(" 2 - GET latest temperature")
        print(" 3 - GET all temperatures")
        print(" 4 - POST test")
        print(" 5 - EXIT")
        choice = input("Select: ")

        if choice == "1":
            temperature = round(random.uniform(15.0, 30.0), 2)
            print(f"[Client] Sending PUT /temperature: {temperature}")
            request = Message(
                mtype = NON,
                code=PUT,
                uri=f"{COAP_PROXY_URI}/temperature",
                payload=str(temperature).encode("utf-8")
            )
        elif choice == "2":
            print("[Client] Sending GET /temperature")
            request = Message(
                mtype=NON,
                code=GET,
                uri=f"{COAP_PROXY_URI}/temperature"
            )
        elif choice == "3":
            print("[Client] Sending GET /temperature?all")
            request = Message(
                mtype=NON,
                code=GET,
                uri=f"{COAP_PROXY_URI}/temperature?all"
            )
        elif choice == "4":
            print("[Client] Sending POST /testpost")
            request = Message(
                mtype=NON,
                code=POST,
                uri=f"{COAP_PROXY_URI}/testpost",
                payload=b"Just testing POST"
            )
        elif choice == "5":
            print("Exiting.")
            break
        else:
            print("Invalid choice.")
            continue

        try:
            response = await context.request(request).response
            print(f"[Client] Response: {response.code}")
            print(f"Payload: {response.payload.decode('utf-8')}")
        except Exception as e:
            print(f"[Client] Request failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())
