from pymodbus.client import ModbusTcpClient
import requests
import time
import os
import sys # Import sys for exit

# Read Modbus target from environment or use default
modbus_ip = os.getenv("MODBUS_IP", '192.168.97.173') # Allow override via env var
modbus_port = int(os.getenv("MODBUS_PORT", "1502")) # Allow override via env var

# Read Gateway endpoint and API Key from environment
# Default to HTTPS endpoint for the Go Gateway
http_endpoint = os.getenv("HTTP_ENDPOINT", "https://go-iot-gateway:8081/data")
gateway_api_key = os.getenv("GATEWAY_API_KEY") # Read from env var (set in docker-compose)

# Check if API Key is set
if not gateway_api_key:
    print("Error: GATEWAY_API_KEY environment variable not set!", flush=True)
    sys.exit(1) # Exit if key is missing

# Initialize Modbus Client
client = ModbusTcpClient(modbus_ip, port=modbus_port, timeout=5) # Increased timeout

# Connection Retry Logic Parameters
retry_interval = 2  # seconds
max_retries = 5

print(f"Modbus Bridge started. Target: {modbus_ip}:{modbus_port}", flush=True)
print(f"HTTP Endpoint: {http_endpoint}", flush=True)


while True:
    try:
        # --- Modbus Connection Handling ---
        if not client.is_socket_open():
            retries = 0
            while retries < max_retries:
                print(f"Attempting to connect to Modbus server at {modbus_ip}:{modbus_port}, attempt {retries + 1}/{max_retries}", flush=True)
                try:
                    client.connect()
                    if client.is_socket_open():
                        print("Successfully connected to Modbus server.", flush=True)
                        break # Exit retry loop on success
                except Exception as e:
                    print(f"Modbus connection error: {e}", flush=True)
                retries += 1
                time.sleep(retry_interval)

            if not client.is_socket_open():
                print(f"Could not connect to Modbus server after {max_retries} retries. Waiting before trying again.", flush=True)
                time.sleep(10) # Wait longer if connection fails repeatedly
                continue # Skip to next main loop iteration

        # --- Modbus Read and HTTP Post ---
        try:
            # Read holding registers (adjust address/count as needed)
            rr = client.read_holding_registers(address=1, count=2, slave=1) # Specify slave unit ID if needed

            if rr.isError():
                print(f"Modbus read error: {rr}", flush=True)
                # Consider closing socket on persistent read errors?
                # client.close()
            elif rr.registers: # Check if registers were actually returned
                # Process data (adjust scaling as needed)
                temp = rr.registers[0] / 10.0
                hum = rr.registers[1] / 10.0
                print(f"Read - Temp: {temp:.1f} °C, Hum: {hum:.1f} %", flush=True)

                # Prepare payload and headers for HTTP POST
                payload = {'temperature': temp, 'humidity': hum, 'source': 'modbus'} # Add source identifier
                headers = {
                    "Content-Type": "application/json",
                    "X-API-Key": gateway_api_key # Add the API Key header
                }

                # Determine SSL verification (disable for internal self-signed certs)
                # CAUTION: Disabling verification is less secure.
                # For production, configure requests to trust your specific CA cert.
                verify_ssl = False if "go-iot-gateway" in http_endpoint else True # Basic check

                # Post data to the Go Gateway (HTTPS)
                try:
                    response = requests.post(http_endpoint, json=payload, headers=headers, verify=verify_ssl, timeout=10) # Add timeout
                    print(f"Posted to HTTP: {response.status_code} {response.reason}", flush=True)
                    # Optionally check response.status_code for errors (e.g., 403 Forbidden)
                    if response.status_code == 403:
                        print("HTTP Error 403: Forbidden. Check GATEWAY_API_KEY.", flush=True)
                    elif response.status_code >= 400:
                         print(f"HTTP Error {response.status_code}: {response.text}", flush=True)

                except requests.exceptions.RequestException as e:
                    print(f"HTTP post error: {e}", flush=True)
            else:
                print("Modbus read successful but returned no registers.", flush=True)


        except Exception as e:
            print(f"Error during Modbus communication or data processing: {e}", flush=True)
            # Close socket on communication error to force reconnect attempt
            if client.is_socket_open():
                client.close()
                print("Closed Modbus socket due to error.", flush=True)

        # Wait before next cycle
        time.sleep(5)

    except KeyboardInterrupt:
        print("Exiting...", flush=True)
        if client.is_socket_open():
            client.close()
        break # Exit the main while loop
    except Exception as e:
        # Catch unexpected errors in the main loop
        print(f"An unexpected error occurred in the main loop: {e}", flush=True)
        if client.is_socket_open():
            client.close()
        print("Waiting before restarting loop...", flush=True)
        time.sleep(10) # Wait before potentially restarting loop after unexpected error