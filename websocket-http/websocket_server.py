import asyncio
import websockets
import requests
import json
import os

# Read HTTP endpoint from environment; defaults to the Go service URL.
http_endpoint = os.getenv("HTTP_ENDPOINT", "http://go-iot-gateway:8080/data")

async def handler(websocket):
    print(f"WebSocket connected from {websocket.remote_address}")
    try:
        async for message in websocket:
            print(f"Received: {message}")
            data = json.loads(message)
            # Forward the received data to the HTTP endpoint.
            response = requests.post(http_endpoint, json=data)
            print(f"Forwarded via HTTP, response: {response.status_code}")
    except websockets.exceptions.ConnectionClosed:
        print("WebSocket disconnected")

async def main():
    # Start the server on port 5000.
    async with websockets.serve(handler, "0.0.0.0", 5000, process_request=None):
        print("WebSocket server started on port 5000")
        await asyncio.Future()  # Run forever

if __name__ == "__main__":
    asyncio.run(main())

