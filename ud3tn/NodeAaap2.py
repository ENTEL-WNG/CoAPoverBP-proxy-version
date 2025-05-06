# NodeAaap2.py: Acts as a CoAP-to-DTN (Delay-Tolerant Networking) proxy for Node A, aggregating CoAP requests and forwarding responses.
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
import sys
import os

# Add aiocoap source to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'aiocoap', 'src'))
sys.path.insert(0, project_root)

from aiocoap import Message
from aiocoap.numbers.optionnumbers import OptionNumber
from ud3tn_utils.aap2.aap2_client import AAP2AsyncUnixClient
from ud3tn_utils.aap2.generated import aap2_pb2

AAP2_SOCKET = "ud3tn-a.aap2.socket"
DEST_EID = "dtn://b.dtn/rec"
COAP_LISTEN_PORT = 5685
MAX_ID = 16777215
current_id = 1

send_client = AAP2AsyncUnixClient(AAP2_SOCKET)
receive_client = AAP2AsyncUnixClient(AAP2_SOCKET)

pending_requests = asyncio.Queue()
pending_tokens = {}

class CoAPListener(asyncio.DatagramProtocol):
    """UDP listener that receives CoAP requests from clients."""
    def connection_made(self, transport):
        self.transport = transport
        print(f"[Node A] Listening on UDP port {COAP_LISTEN_PORT}")

    def datagram_received(self, data, addr):
        print(f"[Node A] Received CoAP packet from {addr}, {len(data)} bytes")
        pending_requests.put_nowait((data, addr))

# Global reference to UDP transport for sending responses
_coap_transport = None

def next_mid():
    """Generate the next message ID."""
    global current_id
    current_id = (current_id % MAX_ID) + 1

def get_transport():
    return _coap_transport

async def dtn_request_loop():
    """Aggregates incoming CoAP requests and sends them over AAP2 bundles."""
    coap_buffer = []
    BUFFER_LIMIT = 5
    TIMEOUT_SECONDS = 10

    async def flush_buffer():
        nonlocal coap_buffer
        if not coap_buffer:
            return
        aggregate_payload = b''.join(coap_buffer)
        adu = aap2_pb2.BundleADU(dst_eid=DEST_EID, payload_length=len(aggregate_payload))
        await send_client.send_adu(adu, aggregate_payload)
        print(f"[Node A] Sent aggregated bundle with {len(coap_buffer)} messages")
        coap_buffer.clear()

    while True:
        try:
            data, addr = await asyncio.wait_for(pending_requests.get(), timeout=TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            await flush_buffer()
            continue

        try:
            original_request = Message.decode(data) 

            original_mid = original_request.mid
            original_client_token = original_request.token
            print(f"[Node A] Received CoAP Message from {addr}: {original_request.code}, Original MID: {original_mid}, Original Token: {original_client_token.hex() if original_client_token else 'None'}")

            new_dtn_token = os.urandom(2) 

            forward_request = Message(
                code=original_request.code,
                payload=original_request.payload,
                mtype=original_request.mtype,
                token=new_dtn_token,
                mid=current_id
            )

            next_mid()

            if forward_request.payload: 
                forward_request.opt.payload_length = len(forward_request.payload)

            if original_request.opt.uri_path == ['']: 
                uri_path_segments = []
            else:
                uri_path_segments = original_request.opt.uri_path

            path = "/" + "/".join(uri_path_segments)
            full_uri = f"coap://b.dtn.arpa:5683{path}" 
            forward_request.set_request_uri(full_uri) 

            pending_tokens[new_dtn_token] = {
                'original_token': original_client_token,
                'original_mid': original_mid,
                'client_address': addr
            }
            print(f"[Node A] Forwarding to DTN: New MID: {forward_request.mid}, New Token: {new_dtn_token.hex()}")

            coap_buffer.append(forward_request.encode()) 

            if len(coap_buffer) >= BUFFER_LIMIT:
                await flush_buffer()

        except Exception as e:
            print(f"[Node A] Failed to decode CoAP message: {e}")
            continue

async def handle_incoming_responses():
    """Receives responses from the DTN and forwards them to original CoAP clients."""
    while True:
        adu_msg, recv_payload = await receive_client.receive_adu()
        print(f"[Node A] Received response from {adu_msg.src_eid}, payload size: {len(recv_payload)} bytes")
        await receive_client.send_response_status(aap2_pb2.ResponseStatus.RESPONSE_STATUS_SUCCESS)

        try:
            response_from_dtn = Message.decode(recv_payload) 
            dtn_token = response_from_dtn.token 

            context = pending_tokens.pop(dtn_token, None)

            if context:
                original_client_token = context['original_token']
                original_mid = context['original_mid']
                client_addr = context['client_address']

                response_from_dtn.token = original_client_token
                response_from_dtn.mid = original_mid
                
                response_payload_to_client = response_from_dtn.encode()

                transport = get_transport()
                transport.sendto(response_payload_to_client, client_addr)
                print(f"[Node A] Forwarded response to {client_addr} (Original MID: {original_mid}, Original Token: {original_client_token.hex() if original_client_token else 'None'})")
            else:
                print(f"[Node A] Unknown token {dtn_token.hex() if dtn_token else 'None'}, cannot forward response")
        except Exception as e:
            print(f"[Node A] Failed to decode response: {e}")

async def main():
    """Initializes the Proxy server and runs DTN and response handlers."""
    global _coap_transport
    loop = asyncio.get_running_loop()
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: CoAPListener(),
        local_addr=("a.dtn.arpa", COAP_LISTEN_PORT)
    )
    _coap_transport = transport

    async with send_client, receive_client:
        await send_client.configure(agent_id="snd")
        await receive_client.configure(agent_id="rec", subscribe=True)

        await asyncio.gather(
            dtn_request_loop(),
            handle_incoming_responses(),
        )

if __name__ == "__main__":
    asyncio.run(main())