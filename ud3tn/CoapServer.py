# CoapServer.py: A dynamic CoAP server that manages resources stored in a JSON file, supporting GET, PUT, POST (create), and DELETE operations.
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
import json

# Add aiocoap source to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'aiocoap', 'src'))
sys.path.insert(0, project_root)

import aiocoap
import aiocoap.resource as resource
from aiocoap.numbers.codes import Code

DATABASE_FILE = 'resources.json'
resources_db = {}

def save_to_file():
    """Save current resources to JSON file."""
    with open(DATABASE_FILE, 'w') as f:
        json.dump(resources_db, f)
    print("[Server] Database saved.")

def load_from_file():
    """Load resources from JSON file if available."""
    global resources_db
    if os.path.exists(DATABASE_FILE):
        with open(DATABASE_FILE, 'r') as f:
            resources_db = json.load(f)
        print("[Server] Database loaded.")
    else:
        print("[Server] No database found, starting fresh.")

class DynamicResource(resource.Resource):
    """A dynamic CoAP resource supporting GET, PUT, and DELETE."""
    def __init__(self, name):
        super().__init__()
        self.name = name
        if self.name not in resources_db:
            resources_db[self.name] = []
            save_to_file()

    async def render_get(self, request):
        data = resources_db.get(self.name, [])
        payload = json.dumps(data).encode('utf-8')
        return aiocoap.Message(code=Code.CONTENT, payload=payload)

    async def render_put(self, request):
        value = request.payload.decode('utf-8')
        resources_db[self.name].append(value)
        save_to_file()
        return aiocoap.Message(code=Code.CHANGED, payload=b"Value appended.")

    async def render_delete(self, request):
        resources_db[self.name] = []
        save_to_file()
        return aiocoap.Message(code=Code.DELETED, payload=b"Resource cleared.")

class DynamicResourceCreator(resource.Resource):
    """Handles POST requests to dynamically create new resources."""
    def __init__(self, root_site):
        super().__init__()
        self.root_site = root_site

    async def render_post(self, request):
        name = request.payload.decode('utf-8').strip()

        if not name:
            return aiocoap.Message(code=Code.BAD_REQUEST, payload=b"Missing resource name.")

        if name in resources_db:
            return aiocoap.Message(code=Code.FORBIDDEN, payload=b"Resource already exists.")

        self.root_site.add_resource((name,), DynamicResource(name))
        resources_db[name] = []
        save_to_file()

        print(f"[Server] Created new resource: {name}")
        return aiocoap.Message(code=Code.CREATED, payload=f"Resource '{name}' created.".encode('utf-8'))

async def main():
    """Starts the CoAP server and loads existing resources."""
    load_from_file()

    root = resource.Site()
    root.add_resource([], DynamicResourceCreator(root))

    for resource_name in resources_db.keys():
        root.add_resource((resource_name,), DynamicResource(resource_name))

    await aiocoap.Context.create_server_context(root, bind=("b.dtn.arpa", 5683))
    print("[Server] CoAP server running at udp://b.dtn.arpa:5683")

    await asyncio.get_running_loop().create_future()

if __name__ == "__main__":
    asyncio.run(main())
