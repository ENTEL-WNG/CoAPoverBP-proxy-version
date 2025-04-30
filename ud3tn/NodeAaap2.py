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

send_client = AAP2AsyncUnixClient(AAP2_SOCKET)
receive_client = AAP2AsyncUnixClient(AAP2_SOCKET)

pending_requests = asyncio.Queue()
pending_tokens = {}  # Map CoAP tokens to client addresses

class CoAPListener(asyncio.DatagramProtocol):
    """UDP listener that receives CoAP requests from clients."""
    def connection_made(self, transport):
        self.transport = transport
        print(f"[Node A] Listening on UDP port {COAP_LISTEN_PORT}")
        self.transport = transport

    def datagram_received(self, data, addr):
        print(f"[Node A] Received CoAP packet from {addr}, {len(data)} bytes")
        pending_requests.put_nowait((data, addr))

# Global reference to UDP transport for sending responses
_coap_transport = None

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
            request = Message.decode(data)
            print(f"[Node A] CoAP Message: {request.code}, MID: {request.mid}, Token: {request.token.hex()}")

            if request.payload:
                request.opt.payload_length = len(request.payload)

            if request.opt.uri_path == ['']:
                request.opt.uri_path = []

            path = "/" + "/".join(request.opt.uri_path)
            full_uri = f"coap://b.dtn.arpa:5683{path}"
            request.set_request_uri(full_uri)

            pending_tokens[request.token] = addr

            coap_buffer.append(request.encode())

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
            response = Message.decode(recv_payload)
            token = response.token
            addr = pending_tokens.pop(token, None)

            if addr:
                transport = get_transport()
                transport.sendto(recv_payload, addr)
                print(f"[Node A] Forwarded response to {addr}")
            else:
                print(f"[Node A] Unknown token {token.hex()}, cannot forward response")
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
