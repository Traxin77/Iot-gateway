import asyncio
from aiocoap import resource, Context, Message, Code
import json
import requests
import os
import sys
import logging # Use logging module

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

# Updated Default HTTP Endpoint
HTTP_ENDPOINT = os.getenv("HTTP_ENDPOINT", "https://go-iot-gateway:8080/data")
GATEWAY_API_KEY = os.getenv("GATEWAY_API_KEY")

if not GATEWAY_API_KEY:
    log.error("GATEWAY_API_KEY environment variable not set!")
    sys.exit(1) # Exit if key is missing

# Determine SSL verification for requests library
verify_ssl = False if "go-iot-gateway" in HTTP_ENDPOINT else True
if not verify_ssl:
    log.warning("SSL verification disabled for Go Gateway endpoint: %s", HTTP_ENDPOINT)
    # Disable requests' warnings about unverified HTTPS requests
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

log.info("CoAP Bridge started.")
log.info("HTTP Endpoint: %s", HTTP_ENDPOINT)
log.info("SSL Verification for HTTP Endpoint: %s", verify_ssl)

class SensorResource(resource.Resource):
    async def render_post(self, request):
        source_addr = request.remote.uri # Get client address if needed
        try:
            payload_str = request.payload.decode('utf-8')
            log.info("CoAP POST received on /sensor/ir from %s", source_addr)
            log.debug("Payload: %s", payload_str)

            try:
                payload_json = json.loads(payload_str)
                # Ensure 'source' identifier is present
                if 'source' not in payload_json:
                     payload_json['source'] = 'coap'
                # Add device identifier if possible (e.g., based on CoAP source address)
                if 'device_id' not in payload_json:
                     payload_json['device_id'] = f"coap_{source_addr}"
            except json.JSONDecodeError:
                 log.warning("Received non-JSON CoAP payload: %s", payload_str)
                 # Wrap non-JSON as a 'value' field
                 payload_json = {'value': payload_str, 'source': 'coap_raw', 'device_id': f"coap_{source_addr}"}

            headers = {
                "Content-Type": "application/json",
                "X-API-Key": GATEWAY_API_KEY, # Add the API Key header
                "X-Source-Identifier": "coap" # Example header to help Go identify source
            }

            # Forwarding to HTTP
            log.debug("Forwarding payload to HTTP: %s", HTTP_ENDPOINT)
            coap_code = Code.INTERNAL_SERVER_ERROR # Default error code
            try:
                # Run synchronous requests.post in executor
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None, # Default executor
                    # Corrected endpoint variable and added verify=verify_ssl
                    lambda: requests.post(HTTP_ENDPOINT, json=payload_json, headers=headers, verify=verify_ssl, timeout=10)
                )

                log.info("HTTP Response: %d %s", response.status_code, response.reason)
                if 200 <= response.status_code < 300:
                    coap_code = Code.CHANGED # Success
                elif response.status_code == 403:
                    log.error("HTTP Error 403: Forbidden. Check GATEWAY_API_KEY.")
                    coap_code = Code.FORBIDDEN
                elif response.status_code == 400:
                    log.error("HTTP Error 400: Bad Request. Check payload format. Response: %s", response.text)
                    coap_code = Code.BAD_REQUEST
                else:
                    log.error("HTTP Error %d: %s", response.status_code, response.text)
                    coap_code = Code.BAD_GATEWAY # Or other suitable 5.xx code

            except requests.exceptions.Timeout:
                log.error("HTTP post timed out to %s", HTTP_ENDPOINT)
                coap_code = Code.GATEWAY_TIMEOUT
            except requests.exceptions.RequestException as e:
                log.error("HTTP post error to %s: %s", HTTP_ENDPOINT, e)
                coap_code = Code.SERVICE_UNAVAILABLE

            # Return success/error to CoAP client
            return Message(code=coap_code, payload=b"Forwarded" if coap_code == Code.CHANGED else b"Error forwarding")

        except UnicodeDecodeError:
            log.error("Failed to decode CoAP payload as UTF-8.")
            return Message(code=Code.BAD_REQUEST, payload=b"Invalid UTF-8 payload")
        except Exception as e:
            log.exception("Error handling CoAP request: %s", e) # Log full traceback
            return Message(code=Code.INTERNAL_SERVER_ERROR, payload=b"Internal Server Error")

async def main():
    log.info("Starting CoAP server on port 5683 (UDP)...")
    root = resource.Site()
    # Define CoAP resources here
    root.add_resource(['sensor', 'ir'], SensorResource()) # Example resource path
    root.add_resource(['data'], SensorResource())        # More generic '/data' endpoint

    bind_addr = '0.0.0.0' # Listen on all IPv4 interfaces
    # bind_addr = '::' # Listen on all IPv6 interfaces (often includes IPv4 too)

    try:
        # Consider adding DTLS context creation here if needed
        await Context.create_server_context(root, bind=(bind_addr, 5683))
        log.info("Listening for CoAP requests on %s:5683...", bind_addr)
        # Keep running forever
        await asyncio.get_running_loop().create_future()
    except OSError as e:
         log.error("Error starting CoAP server (maybe port 5683 is in use?): %s", e)
    except Exception as e:
         log.exception("Unexpected error during CoAP server setup: %s", e) # Log traceback

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("CoAP server stopped by user.")

