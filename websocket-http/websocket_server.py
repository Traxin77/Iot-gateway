import asyncio
import websockets
import requests
import json
import os
import ssl
import logging # Use logging
import sys
import urllib3 # For disabling SSL warnings

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

http_endpoint = os.getenv("HTTP_ENDPOINT", "https://go-iot-gateway:8080/data")
gateway_api_key = os.getenv("GATEWAY_API_KEY")
ws_port = int(os.getenv("WS_PORT", "8765")) # Use different port from Go UI/WS (8081)
cert_file = os.getenv("WS_CERT_FILE") # Optional: Path to cert for WSS
key_file = os.getenv("WS_KEY_FILE")   # Optional: Path to key for WSS

# --- Initial Checks ---
if not gateway_api_key:
    log.error("GATEWAY_API_KEY environment variable not set!")
    sys.exit(1)

# Determine SSL verification for requests library
verify_ssl = False if "go-iot-gateway" in http_endpoint else True
if not verify_ssl:
    log.warning("SSL verification disabled for Go Gateway endpoint: %s", http_endpoint)
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

log.info("WebSocket Bridge started.")
log.info("HTTP Endpoint: %s", http_endpoint)
log.info("SSL Verification for HTTP Endpoint: %s", verify_ssl)
log.info("WebSocket Port: %d", ws_port)

async def handler(websocket, path): # Added path argument (though not used here)
    client_addr = websocket.remote_address
    log.info("WebSocket connected from %s", client_addr)
    try:
        async for message in websocket:
            log.debug("Received from %s: %s...", client_addr, message[:100]) # Log truncated message
            try:
                # Assume JSON, attempt parsing
                data = json.loads(message)

                # Add source/device info if missing
                if 'source' not in data:
                    data['source'] = 'websocket'
                if 'device_id' not in data:
                    data['device_id'] = f"ws_{client_addr[0]}_{client_addr[1]}" # Example ID from address

                # Forward the received data via HTTPS with API Key
                headers = {
                    "Content-Type": "application/json",
                    "X-API-Key": gateway_api_key, # Add API Key header
                    "X-Source-Identifier": "websocket" # Example header
                }

                try:
                     log.debug("Forwarding payload to HTTP endpoint: %s", http_endpoint)
                     # Use run_in_executor for synchronous requests call
                     loop = asyncio.get_event_loop()
                     response = await loop.run_in_executor(
                          None, # Default executor
                          lambda: requests.post(http_endpoint, json=data, headers=headers, verify=verify_ssl, timeout=10)
                     )
                     log.info("Forwarded via HTTP, response: %d %s", response.status_code, response.reason)
                     # Check for HTTP errors
                     if response.status_code == 403:
                         log.error("HTTP Error 403: Forbidden. Check GATEWAY_API_KEY.")
                     elif response.status_code == 400:
                         log.error("HTTP Error 400: Bad Request. Check payload format. Response: %s", response.text)
                     elif response.status_code >= 500:
                           log.error("HTTP Server Error %d: %s", response.status_code, response.text)

                     # Optional: Send confirmation back to WebSocket client
                     # await websocket.send(json.dumps({"status": "received", "code": response.status_code}))

                except requests.exceptions.Timeout:
                    log.error("HTTP post timed out to %s", http_endpoint)
                    # await websocket.send(json.dumps({"status": "error", "message": "Gateway timeout"}))
                except requests.exceptions.RequestException as e:
                     log.error("Error sending data to HTTP endpoint %s: %s", http_endpoint, e)
                     # await websocket.send(json.dumps({"status": "error", "message": "Gateway connection error"}))

            except json.JSONDecodeError:
                log.warning("Received non-JSON WebSocket message from %s: %s...", client_addr, message[:100])
                # await websocket.send(json.dumps({"status": "error", "message": "Invalid JSON format"}))
            except Exception as e:
                 log.exception("Error processing WebSocket message from %s: %s", client_addr, e) # Log traceback
                 # await websocket.send(json.dumps({"status": "error", "message": "Internal server error"}))

    except websockets.exceptions.ConnectionClosedOK:
        log.info("WebSocket disconnected gracefully from %s", client_addr)
    except websockets.exceptions.ConnectionClosedError as e:
         log.warning("WebSocket disconnected with error from %s: %s", client_addr, e)
    except Exception as e:
        log.exception("Unexpected error in WebSocket handler for %s: %s", client_addr, e) # Log traceback
    finally:
         log.info("WebSocket connection handler finished for %s", client_addr)


async def main():
    # Configure TLS (SSL) context for WSS if cert/key paths are provided and exist
    ssl_context = None
    protocol = "WS"
    if cert_file and key_file:
        log.info("Checking for TLS cert=%s, key=%s", cert_file, key_file)
        if os.path.exists(cert_file) and os.path.exists(key_file):
            try:
                ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                ssl_context.load_cert_chain(cert_file, key_file)
                protocol = "WSS (TLS)"
                log.info("TLS context created successfully.")
            except FileNotFoundError:
                 log.error("TLS certificate or key file not found (%s / %s). Starting WS without TLS.", cert_file, key_file)
                 ssl_context = None # Fallback to non-TLS
            except Exception as e:
                log.exception("Error loading TLS cert/key: %s. Starting WS without TLS.", e) # Log traceback
                ssl_context = None # Fallback to non-TLS
        else:
            log.warning("TLS cert/key files specified but not found. Starting WS without TLS.")
    else:
        log.info("TLS cert/key files not specified. Starting WebSocket server without TLS (WS).")

    bind_addr = "0.0.0.0" # Listen on all interfaces
    log.info("Starting %s server on %s:%d", protocol, bind_addr, ws_port)

    # Start the server with or without TLS
    try:
        async with websockets.serve(handler, bind_addr, ws_port, ssl=ssl_context):
            await asyncio.Future() # Run forever
    except OSError as e:
        log.error("Error starting WebSocket server (maybe port %d is in use?): %s", ws_port, e)
    except Exception as e:
        log.exception("Unexpected error during WebSocket server startup: %s", e) # Log traceback


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("WebSocket server stopped by user.")
