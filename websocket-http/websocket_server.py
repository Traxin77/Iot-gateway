import asyncio
import websockets
import requests
import json
import os
import ssl

# Read HTTP endpoint from environment; defaults to the Go service URL.
http_endpoint = os.getenv("HTTP_ENDPOINT", "https://go-iot-gateway:8081/data") # Default to HTTPS
gateway_api_key = os.getenv("GATEWAY_API_KEY")
ws_port = int(os.getenv("WS_PORT", "5000"))
cert_file = os.getenv("WS_CERT_FILE", "certs/server.crt") # Path to cert
key_file = os.getenv("WS_KEY_FILE", "certs/server.key")   # Path to key

if not gateway_api_key:
    print("Error: GATEWAY_API_KEY environment variable not set!", flush=True)
    exit(1)

async def handler(websocket):
    print(f"WebSocket connected from {websocket.remote_address}", flush=True)
    try:
        async for message in websocket:
            print(f"Received: {message[:100]}...", flush=True) # Log truncated message
            try:
                data = json.loads(message)
                # --> Forward the received data via HTTPS with API Key <--
                headers = {
                    "Content-Type": "application/json",
                    "X-API-Key": gateway_api_key # Add API Key header
                }
                # Handle potential self-signed certs for internal HTTPS
                verify_ssl = False if "go-iot-gateway" in http_endpoint else True

                response = requests.post(http_endpoint, json=data, headers=headers, verify=verify_ssl)
                print(f"Forwarded via HTTP, response: {response.status_code}", flush=True)
            except json.JSONDecodeError:
                print(f"Error: Received non-JSON message: {message[:100]}...", flush=True)
            except requests.exceptions.RequestException as e:
                 print(f"Error sending data to HTTP endpoint {http_endpoint}: {e}", flush=True)
            except Exception as e:
                 print(f"Error processing message: {e}", flush=True)

    except websockets.exceptions.ConnectionClosedOK:
        print(f"WebSocket disconnected gracefully from {websocket.remote_address}", flush=True)
    except websockets.exceptions.ConnectionClosedError as e:
         print(f"WebSocket disconnected with error from {websocket.remote_address}: {e}", flush=True)
    except Exception as e:
        print(f"Unexpected error in handler: {e}", flush=True)
async def main():
    # --> Configure TLS for WebSocket Server <--
    ssl_context = None
    if os.path.exists(cert_file) and os.path.exists(key_file):
        print(f"Loading TLS cert={cert_file}, key={key_file}", flush=True)
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        try:
            ssl_context.load_cert_chain(cert_file, key_file)
            print(f"WebSocket server starting with TLS (WSS) on port {ws_port}", flush=True)
        except FileNotFoundError:
             print(f"Error: TLS certificate or key file not found ({cert_file} / {key_file}). Starting WS without TLS.", flush=True)
             ssl_context = None # Fallback to non-TLS
        except Exception as e:
            print(f"Error loading TLS cert/key: {e}. Starting WS without TLS.", flush=True)
            ssl_context = None # Fallback to non-TLS
    else:
        print(f"TLS cert/key files not found. Starting WebSocket server without TLS (WS) on port {ws_port}", flush=True)

    # --> Start the server with or without TLS <--
    async with websockets.serve(handler, "0.0.0.0", ws_port, ssl=ssl_context):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())

