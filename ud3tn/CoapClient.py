# CoapClient.py: An interactive console-based CoAP client for sending POST, PUT, GET, and DELETE requests to a specified CoAP proxy.
# Copyright (C) 2025  Michael Karpov
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import asyncio
import aioconsole
import os
import sys

# Add aiocoap source to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'aiocoap', 'src'))
sys.path.insert(0, project_root)

from aiocoap import Context, Message
from aiocoap.numbers.codes import Code
from aiocoap.numbers.types import Type

COAP_PROXY_URI = "coap://a.dtn.arpa:5685"  # Proxy address on Node A

async def send_and_print(request, context):
    """Send a CoAP request and print the response."""
    try:
        response = await context.request(request).response
        print("\nReceived response:")
        print(f"  Code: {response.code}")
        print(f"  Payload: {response.payload.decode('utf-8', errors='ignore')}")
    except Exception as e:
        print(f"[Client] Request failed: {e}")

async def main():
    """Interactive console-based CoAP client."""
    context = await Context.create_client_context()

    while True:
        print("Commands: post, put, get, delete, exit")
        cmd = (await aioconsole.ainput("Enter command: ")).strip().lower()

        if cmd == "exit":
            print("Exiting client.")
            break

        # Build request
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

        # Dispatch request
        asyncio.create_task(send_and_print(request, context))
        print(f"[Client] Dispatched {cmd.upper()} -> {uri}")

    await asyncio.sleep(0.1)
    print("Goodbye!")

if __name__ == "__main__":
    asyncio.run(main())
