import asyncio
from aiocoap import *
from aiocoap.numbers.codes import Code
from ud3tn_utils.aap2.aap2_client import AAP2AsyncUnixClient
from ud3tn_utils.aap2.generated import aap2_pb2

AAP2_SOCKET = "ud3tn-b.aap2.socket"
COAP_SERVER_URI = "coap://localhost" # Local CoAP server on Node B

send_client = AAP2AsyncUnixClient(AAP2_SOCKET)
receive_client = AAP2AsyncUnixClient(AAP2_SOCKET)

# Forwards decoded CoAP request to local CoAP server
async def forward_to_coap_server(coap_bytes):
    try:
        protocol = await Context.create_client_context()
        original = Message.decode(coap_bytes)

        path = "/" + "/".join(original.opt.uri_path)
        full_uri = f"coap://localhost:5688{path}"

        forwarded = Message(
            code=original.code,
            uri=full_uri,
            payload=original.payload,
            mtype=original.mtype,
        )
        print(f"[Node B] Forwarding CoAP")

        response = await protocol.request(forwarded).response

        # Preserve original metadata
        response.token = original.token
        response.mid = original.mid

        print(f"[Node B] CoAP server replied")

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

# Main loop: receive BP messages, call forwarder, send response back over BP
async def bundle_to_coap_bridge():
    async with send_client, receive_client:
        await send_client.configure(agent_id="snd")
        await receive_client.configure(agent_id="rec", subscribe=True)

        print("[Node B] Listening for incoming bundles...")

        while True:
            adu_msg, recv_payload = await receive_client.receive_adu()
            print(f"[Node B] Received ADU from {adu_msg.src_eid}, payload size: {len(recv_payload)} bytes")

            await receive_client.send_response_status(aap2_pb2.ResponseStatus.RESPONSE_STATUS_SUCCESS)

            coap_response_bytes = await forward_to_coap_server(recv_payload)

            # Send response back to Node A
            response_adu = aap2_pb2.BundleADU(
                dst_eid="dtn://a.dtn/rec",
                payload_length=len(coap_response_bytes)
            )
            await send_client.send_adu(response_adu, coap_response_bytes)


if __name__ == "__main__":
    asyncio.run(bundle_to_coap_bridge())
