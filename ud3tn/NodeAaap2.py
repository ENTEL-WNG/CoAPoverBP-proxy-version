# AAP2 client setup and asyncio tools
import asyncio
from aiocoap import Message
from ud3tn_utils.aap2.aap2_client import AAP2AsyncUnixClient
from ud3tn_utils.aap2.generated import aap2_pb2

# Node A setup
AAP2_SOCKET = "ud3tn-a.aap2.socket" # Path to UD3TN AAP2 socket on Node A
DEST_EID = "dtn://b.dtn/rec"        # Destination EID (Node B receiver)
COAP_LISTEN_PORT = 5685             # CoAP port

# Async AAP2 clients for send/receive
send_client = AAP2AsyncUnixClient(AAP2_SOCKET)
receive_client = AAP2AsyncUnixClient(AAP2_SOCKET)

# Queue for pending CoAP requests
pending_requests = asyncio.Queue()

# Listener that collects incoming CoAP messages
class CoAPListener(asyncio.DatagramProtocol):
    def connection_made(self, transport):
        self.transport = transport
        print(f"[Node A] Listening on UDP port {COAP_LISTEN_PORT}")
        self.transport = transport

    def datagram_received(self, data, addr):
        print(f"[Node A] Received CoAP packet from {addr}, {len(data)} bytes")
        pending_requests.put_nowait((data, addr))

# Main loop: receives CoAP, sends it via BP, waits for a response, sends it back to CoAP client
async def dtn_request_loop():
    while True:
        data, addr = await pending_requests.get()

        try:
            request = Message.decode(data)
            print(f"[Node A] CoAP Message: {request.code}, MID: {request.mid}, Token: {request.token.hex()}")
        except Exception as e:
            print(f"[Node A] Failed to decode CoAP message: {e}")
            continue

        # Send over BP via AAP2
        adu = aap2_pb2.BundleADU(dst_eid=DEST_EID, payload_length=len(data))
        await send_client.send_adu(adu, data)
        print(f"[Node A] Sent CoAP message into bundle network")

        # Wait for BP response
        adu_msg, recv_payload = await receive_client.receive_adu()
        await receive_client.send_response_status(aap2_pb2.ResponseStatus.RESPONSE_STATUS_SUCCESS)
        print(f"[Node A] Received response from {adu_msg.src_eid}, sending to {addr}")

        # Forward response to original CoAP client
        transport = get_transport()
        transport.sendto(recv_payload, addr)

# Transport is stored globally for reply access
_coap_transport = None
def get_transport():
    return _coap_transport

# Start listener and proxy loop
async def main():
    global _coap_transport

    loop = asyncio.get_running_loop()
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: CoAPListener(),
        local_addr=("localhost", COAP_LISTEN_PORT)
    )
    _coap_transport = transport

    async with send_client, receive_client:
        await send_client.configure(agent_id="snd")
        await receive_client.configure(agent_id="rec", subscribe=True)

        await dtn_request_loop() 


if __name__ == "__main__":
    asyncio.run(main())
