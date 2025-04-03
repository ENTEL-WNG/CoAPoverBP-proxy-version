import asyncio
import aiocoap.resource as resource
import aiocoap
from aiocoap.numbers.codes import Code

# Temperature storage and dynamic resource handling
class TemperatureResource(resource.Resource):
    def __init__(self):
        super().__init__()
        self.temperatures = []

    async def render_get(self, request):
        if "all" in request.opt.uri_query:
            print("GET all")
            payload = ", ".join(map(str, self.temperatures)).encode("utf-8")
        else:
            print("GET 1")
            payload = (
                str(self.temperatures[-1]).encode("utf-8")
                if self.temperatures
                else b"No temperatures recorded."
            )
        return aiocoap.Message(code=Code.CONTENT, payload=payload)

    async def render_put(self, request):
        try:
            temperature = float(request.payload.decode("utf-8"))
            self.temperatures.append(temperature)
            print(f"Received temperature: {temperature}")
            return aiocoap.Message(code=Code.CHANGED, payload=b"Temperature recorded.")
        except ValueError:
            return aiocoap.Message(code=Code.BAD_REQUEST, payload=b"Invalid temperature.")


class DummyPOST(resource.Resource):
    def __init__(self):
        super().__init__()

    async def render_post(self, request):
        print("Received POST request")
        return aiocoap.Message(code=Code.CHANGED, payload=b"POST received")


class DynamicResource(resource.Resource):
    def __init__(self, initial_data=""):
        super().__init__()
        self.data = initial_data

    async def render_get(self, request):
        return aiocoap.Message(code=Code.CONTENT, payload=self.data.encode('utf-8'))

    async def render_post(self, request):
        payload = request.payload.decode('utf-8')
        self.data += f"\n{payload}"
        return aiocoap.Message(code=Code.CHANGED, payload=b"Data added")


class DynamicResourceCreator(resource.Resource):
    def __init__(self, root_site):
        super().__init__()
        self.root_site = root_site

    async def render_post(self, request):
        resource_id = request.opt.uri_path[-1]
        if resource_id in self.root_site._resources:
            return aiocoap.Message(payload=b"Resource already exists.", code=Code.FORBIDDEN)

        payload = request.payload.decode('utf-8')
        new_resource = DynamicResource(initial_data=payload)
        self.root_site.add_resource((resource_id,), new_resource)

        return aiocoap.Message(
            payload=f"Resource '{resource_id}' created.".encode('utf-8'),
            code=Code.CREATED
        )

# Start CoAP server
async def main():
    root = resource.Site()
    root.add_resource(["temperature"], TemperatureResource())
    root.add_resource(["testpost"], DummyPOST())
    root.add_resource(["create"], DynamicResourceCreator(root))

    await aiocoap.Context.create_server_context(root, bind=("localhost", 5688))
    print("CoAP Server is running on udp://localhost:5683")

    await asyncio.get_running_loop().create_future()


if __name__ == "__main__":
    asyncio.run(main())
