import asyncio
from aiocoap import resource, Context, Message, Code
import json
import requests
import os 
HTTP_SERVER_URL = os.getenv("HTTP_ENDPOINT", "http://go-iot-gateway:8080/data")

class SensorResource(resource.Resource):
    async def render_post(self, request):
        try:
            payload = request.payload.decode('utf-8')
            print(f"[+] CoAP POST received on /sensor/ir")
            print(f"Payload: {payload}")

            # Forwarding to HTTP
            print(f"[>] Forwarding payload to HTTP: {HTTP_SERVER_URL}")
            response = requests.post(HTTP_SERVER_URL, json=json.loads(payload))
            print(f"[<] HTTP Response: {response.status_code} {response.text}")

            return Message(code=Code.CHANGED, payload=b"OK")
        except Exception as e:
            print(f"[!] Error handling request: {e}")
            return Message(code=Code.INTERNAL_SERVER_ERROR, payload=b"ERROR")

async def main():
    print("[*] Starting CoAP server on port 5683 (UDP)...")
    root = resource.Site()
    root.add_resource(['sensor', 'ir'], SensorResource())

    await Context.create_server_context(root, bind=('0.0.0.0', 5683))
    print("[*] Listening for CoAP requests...")

    # Keep running forever
    await asyncio.get_running_loop().create_future()

if __name__ == "__main__":
    asyncio.run(main())

