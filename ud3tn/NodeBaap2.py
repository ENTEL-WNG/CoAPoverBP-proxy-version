import asyncio
import sys
import os
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'aiocoap', 'src'))
sys.path.insert(0, project_root)
from aiocoap import *
from aiocoap.numbers.codes import Code
from ud3tn_utils.aap2.aap2_client import AAP2AsyncUnixClient
from ud3tn_utils.aap2.generated import aap2_pb2

AAP2_SOCKET = "ud3tn-b.aap2.socket"
COAP_SERVER_URI = "coap://localhost" # Local CoAP server on Node B

send_client = AAP2AsyncUnixClient(AAP2_SOCKET)
receive_client = AAP2AsyncUnixClient(AAP2_SOCKET)

# Forwards decoded CoAP request to local CoAP server
async def forward_to_coap_server(coap_bytes, payload_length):
    try:
        protocol = await Context.create_client_context()
        original = Message.decode(coap_bytes)

        if original.opt.uri_path == ['']:
            original.opt.uri_path = []

        path = "/" + "/".join(original.opt.uri_path)
        full_uri = f"coap://localhost:5683{path}"

        forwarded = Message(
            code=original.code,
            uri=full_uri,
            payload=original.payload,
            mtype=original.mtype,   
            payload_length=payload_length
        )
        print(f"[Node B] Forwarding CoAP:")
        print(f"  Method: {original.code}")
        print(f"  URI Path: {original.opt.uri_path}")
        print(f"  Full URI: {full_uri}")
        print(f"  Payload: {original.payload}")

        response = await protocol.request(forwarded).response

        print(f"[Node B] CoAP server replied")

        print(f"[LOG] INCOMING -> MID: {response.mid}, Token: {response.token.hex()}")

        # Preserve original metadata
        response.token = original.token
        response.mid = original.mid

        print(f"[LOG] OUTGOING TO CLIENT -> MID: {response.mid}, Token: {response.token.hex()}")

        return response.encode()

    except Exception as e:
        print(f"[Node B] CoAP forwarding error: {e}")
        # Return fallback error response
        error_response = Message(
            code=Code.INTERNAL_SERVER_ERROR,
            payload=b"Server error (node B)"
        )
        error_response.mtype = 0
        error_response.mid = 0
        error_response.token = b'\x00'
        return error_response.encode()


async def bundle_to_coap_bridge():
    async with send_client, receive_client:
        await send_client.configure(agent_id="snd")
        await receive_client.configure(agent_id="rec", subscribe=True)

        print("[Node B] Listening for incoming bundles...")

        while True:
            adu_msg, recv_payload = await receive_client.receive_adu()
            print(f"[Node B] Received ADU from {adu_msg.src_eid}, payload size: {len(recv_payload)} bytes")

            await receive_client.send_response_status(aap2_pb2.ResponseStatus.RESPONSE_STATUS_SUCCESS)

            offset = 0
            while offset < len(recv_payload):
                partial = recv_payload[offset:]
                try:
                    msg = Message.decode(partial)

                    if not msg.opt.payload_length:
                        raise ValueError("Missing Payload-Length option in aggregated message")

                    payload_length = msg.opt.payload_length

                    # Re-encode the full message (header + options + 0xFF + payload)
                    full_encoded = msg.encode()

                    # Find where 0xFF (Payload Marker) is
                    payload_marker_index = full_encoded.find(b'\xFF')
                    if payload_marker_index == -1:
                        raise ValueError("Payload Marker (0xFF) not found in CoAP message")

                    # Full message length = marker index + 1 (marker byte) + payload length
                    full_message_length = payload_marker_index + 1 + payload_length

                    print(f"[Node B] Parsed CoAP message, payload length: {payload_length}, total length: {full_message_length}")

                    coap_bytes = recv_payload[offset:offset+full_message_length]
                    offset += full_message_length

                    coap_response_bytes = await forward_to_coap_server(coap_bytes, payload_length)

                    response_adu = aap2_pb2.BundleADU(
                        dst_eid="dtn://a.dtn/rec",
                        payload_length=len(coap_response_bytes)
                    )
                    await send_client.send_adu(response_adu, coap_response_bytes)

                except Exception as e:
                    print(f"[Node B] Failed to parse CoAP message from aggregate: {e}")
                    break


if __name__ == "__main__":
    asyncio.run(bundle_to_coap_bridge())