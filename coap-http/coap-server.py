import asyncio
from aiocoap import resource, Context, Message, Code
import json
import requests
import os
import sys

HTTP_SERVER_URL = os.getenv("HTTP_ENDPOINT", "http://go-iot-gateway:8080/data")
GATEWAY_API_KEY = os.getenv("GATEWAY_API_KEY")

if not GATEWAY_API_KEY:
    print("Error: GATEWAY_API_KEY environment variable not set!", flush=True)
    sys.exit(1) # Exit if key is missing

print(f"CoAP Bridge started.", flush=True)
print(f"HTTP Endpoint: {HTTP_ENDPOINT}", flush=True)
class SensorResource(resource.Resource):
    async def render_post(self, request):
        try:
            payload = request.payload.decode('utf-8')
            print(f"[+] CoAP POST received on /sensor/ir")
            print(f"Payload: {payload_str}",flush=True)

            try:
                payload_json = json.loads(payload_str)
                # Add source identifier if not present
                if 'source' not in payload_json:
                     payload_json['source'] = 'coap'
            except json.JSONDecodeError:
                 print(f"[!] Error: Received non-JSON CoAP payload: {payload_str}", flush=True)
                 # Decide how to handle non-JSON: error out or wrap it
                 # Example: Wrap non-JSON as a 'value' field
                 payload_json = {'value': payload_str, 'source': 'coap_raw'}
            headers = {
                "Content-Type": "application/json",
                "X-API-Key": GATEWAY_API_KEY # Add the API Key header
            }
            verify_ssl = False if "go-iot-gateway" in HTTP_ENDPOINT else True
            # Forwarding to HTTP
            print(f"[>] Forwarding payload to HTTP: {HTTP_SERVER_URL}")
            
            try:
                # Send the potentially modified payload_json
                response = requests.post(HTTP_ENDPOINT, json=payload_json, headers=headers, verify=verify_ssl, timeout=10) # Add headers, verify, timeout
                print(f"[<] HTTP Response: {response.status_code} {response.reason}", flush=True)
                 # Optionally check response.status_code for errors
                if response.status_code == 403:
                    print("HTTP Error 403: Forbidden. Check GATEWAY_API_KEY.", flush=True)
                elif response.status_code >= 400:
                    print(f"HTTP Error {response.status_code}: {response.text}", flush=True)

            except requests.exceptions.RequestException as e:
                print(f"[!] HTTP post error: {e}", flush=True)
                # Return error to CoAP client if HTTP forward fails
                return Message(code=Code.SERVICE_UNAVAILABLE, payload=b"Failed to forward data")

            # Return success to CoAP client
            return Message(code=Code.CHANGED, payload=b"OK")
        except Exception as e:
            print(f"[!] Error handling request: {e}")
            return Message(code=Code.INTERNAL_SERVER_ERROR, payload=b"ERROR")

async def main():
    print("[*] Starting CoAP server on port 5683 (UDP)...",flush=True)
    root = resource.Site()
    root.add_resource(['sensor', 'ir'], SensorResource())
    try:
        await Context.create_server_context(root, bind=('0.0.0.0', 5683))
        print("[*] Listening for CoAP requests...", flush=True)

        # Keep running forever
        await asyncio.get_running_loop().create_future()
    except OSError as e:
         print(f"[!] Error starting CoAP server (maybe port 5683 is in use?): {e}", flush=True)
    except Exception as e:
         print(f"[!] Unexpected error during CoAP server setup: {e}", flush=True)

if __name__ == "__main__":
    asyncio.run(main())

