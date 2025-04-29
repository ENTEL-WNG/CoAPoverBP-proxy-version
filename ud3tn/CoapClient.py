# CoapClient.py

import asyncio
import aioconsole
import os
import sys

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'aiocoap', 'src'))
sys.path.insert(0, project_root)
from aiocoap import Context, Message
from aiocoap.numbers.codes import Code
from aiocoap.numbers.types import Type

COAP_PROXY_URI = "coap://a.dtn.arpa:5685"  # Local proxy port on Node A

async def send_and_print(request, context):
    try:
        response = await context.request(request).response
        print("\nReceived response:")
        print(f"  Code: {response.code}")
        print(f"  Payload: {response.payload.decode('utf-8', errors='ignore')}")
    except Exception as e:
        print(f"[Client] Request failed: {e}")

async def main():
    context = await Context.create_client_context()

    while True:
        print("Commands: post, put, get, delete, exit")
        cmd = (await aioconsole.ainput("Enter command: ")).strip().lower()

        if cmd == "exit":
            print("Exiting client.")
            break

        # build request + remember its URI
        if cmd == "post":
            name = await aioconsole.ainput("Enter new resource name: ")
            uri = COAP_PROXY_URI + "/"
            request = Message(
                code=Code.POST,
                uri=uri,
                mtype=Type.NON,
                payload=name.encode('utf-8')
            )

        elif cmd == "put":
            name = await aioconsole.ainput("Enter resource name to PUT to: ")
            val  = await aioconsole.ainput("Enter value to PUT: ")
            uri = f"{COAP_PROXY_URI}/{name}"
            request = Message(
                code=Code.PUT,
                uri=uri,
                mtype=Type.NON,
                payload=val.encode('utf-8')
            )

        elif cmd == "get":
            name = await aioconsole.ainput("Enter resource name to GET: ")
            uri = f"{COAP_PROXY_URI}/{name}"
            request = Message(
                code=Code.GET,
                uri=uri,
                mtype=Type.NON,
                payload=b"get"
            )

        elif cmd == "delete":
            name = await aioconsole.ainput("Enter resource name to DELETE: ")
            uri = f"{COAP_PROXY_URI}/{name}"
            request = Message(
                code=Code.DELETE,
                uri=uri,
                mtype=Type.NON,
                payload=b"delete"
            )

        else:
            print("Unknown command.")
            continue

        # dispatch asynchronously
        asyncio.create_task(send_and_print(request, context))
        print(f"[Client] Dispatched {cmd.upper()} -> {uri}")

    # give any in-flight tasks a moment before exit
    await asyncio.sleep(0.1)
    print("Goodbye!")

if __name__ == "__main__":
    asyncio.run(main())
