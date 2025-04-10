# --- modbus-http/modbus_client.py (Replace relevant lines) ---
import requests
import time
import os
import sys
import logging
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ConnectionException

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

modbus_ip = os.getenv("MODBUS_IP", '192.168.1.100') 
modbus_port = int(os.getenv("MODBUS_PORT", "502"))
modbus_slave_id = int(os.getenv("MODBUS_SLAVE_ID", "1"))
poll_interval = int(os.getenv("POLL_INTERVAL", "5")) # Default 5 seconds

# Read Gateway endpoint and API Key from environment
# Updated Default HTTP Endpoint port to 8080
http_endpoint = os.getenv("HTTP_ENDPOINT", "https://go-iot-gateway:8080/data")
gateway_api_key = os.getenv("GATEWAY_API_KEY") # Read from env var

# Check if API Key is set
if not gateway_api_key:
    log.error("GATEWAY_API_KEY environment variable not set!")
    sys.exit(1) # Exit if key is missing

# Determine SSL verification for requests library
verify_ssl = False if "go-iot-gateway" in http_endpoint else True
if not verify_ssl:
    log.warning("SSL verification disabled for Go Gateway endpoint: %s", http_endpoint)
    # Disable requests' warnings about unverified HTTPS requests
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Initialize Modbus Client outside the loop
client = ModbusTcpClient(modbus_ip, port=modbus_port, timeout=5) # Increased timeout

# Connection Retry Logic Parameters
retry_interval = 3  # seconds
max_retries = 5

log.info("Modbus Bridge started.")
log.info("Target: %s:%d (Slave ID: %d)", modbus_ip, modbus_port, modbus_slave_id)
log.info("Poll Interval: %d seconds", poll_interval)
log.info("HTTP Endpoint: %s", http_endpoint)
log.info("SSL Verification for HTTP Endpoint: %s", verify_ssl)

while True:
    try:
        # --- Modbus Connection Handling ---
        if not client.is_socket_open():
            retries = 0
            connected = False
            while retries < max_retries:
                log.info("Attempting to connect to Modbus server at %s:%d, attempt %d/%d", modbus_ip, modbus_port, retries + 1, max_retries)
                try:
                    connected = client.connect() # Returns True on success, False otherwise
                    if connected:
                        log.info("Successfully connected to Modbus server.")
                        break # Exit retry loop on success
                    else:
                         log.warning("Modbus connection attempt failed (client.connect returned False).")
                except ConnectionException as e: # Catch specific pymodbus exception
                    log.error("Modbus connection error: %s", e)
                except Exception as e: # Catch other potential errors
                    log.exception("Unexpected error during Modbus connection attempt: %s", e)

                retries += 1
                time.sleep(retry_interval * (retries)) # Exponential backoff for retries

            if not connected:
                log.error("Could not connect to Modbus server after %d retries. Waiting %d seconds before trying again.", max_retries, poll_interval * 2)
                time.sleep(poll_interval * 2) # Wait longer if connection fails repeatedly
                continue # Skip to next main loop iteration

        # --- Modbus Read and HTTP Post ---
        try:
            # Example: Read 2 holding registers starting from address 1
            # Adjust address, count, and function (read_holding_registers, read_input_registers, etc.) as needed
            log.debug("Reading Modbus registers...")
            rr = client.read_holding_registers(address=1, count=2, slave=modbus_slave_id)

            if rr.isError():
                log.error("Modbus read error: %s", rr)
                # Consider closing socket on persistent read errors? Maybe after N consecutive errors.
                # client.close()
            elif rr.registers: # Check if registers were actually returned
                # --- Process Data (Adapt this section based on your device) ---
                # Example assumes registers 0 and 1 hold temp/hum scaled by 10
                temp = rr.registers[0] / 10.0
                hum = rr.registers[1] / 10.0
                log.info("Read - Temp: %.1f C, Hum: %.1f %%", temp, hum)

                # Prepare payload and headers for HTTP POST
                payload = {
                    'temperature': temp,
                    'humidity': hum,
                    'source': 'modbus', # Add source identifier
                    'device_id': f"modbus_{modbus_ip}_{modbus_slave_id}" # Example device ID
                 }
                headers = {
                    "Content-Type": "application/json",
                    "X-API-Key": gateway_api_key, # Add the API Key header
                    "X-Source-Identifier": "modbus" # Example header
                }

                # Post data to the Go Gateway (HTTPS)
                try:
                    log.debug("Posting data to HTTP endpoint: %s", http_endpoint)
                    response = requests.post(http_endpoint, json=payload, headers=headers, verify=verify_ssl, timeout=10) # Added timeout
                    log.info("Posted to HTTP: %d %s", response.status_code, response.reason)
                    # Optionally check response.status_code for errors
                    if response.status_code == 403:
                        log.error("HTTP Error 403: Forbidden. Check GATEWAY_API_KEY.")
                    elif response.status_code == 400:
                        log.error("HTTP Error 400: Bad Request. Check payload format. Response: %s", response.text)
                    elif response.status_code >= 500:
                         log.error("HTTP Server Error %d: %s", response.status_code, response.text)

                except requests.exceptions.Timeout:
                    log.error("HTTP post timed out to %s", http_endpoint)
                except requests.exceptions.RequestException as e:
                    log.error("HTTP post error to %s: %s", http_endpoint, e)
            else:
                log.warning("Modbus read successful but returned no registers.")


        except ConnectionException as e: # Catch specific communication errors
             log.error("Modbus communication error during read: %s. Closing connection.", e)
             client.close()
        except Exception as e:
            log.exception("Error during Modbus data processing or HTTP post: %s", e) # Log traceback
            # Decide if connection should be closed on generic errors
            if client.is_socket_open():
                 client.close()
                 log.info("Closed Modbus socket due to processing error.")

        # Wait before next poll cycle
        log.debug("Waiting %d seconds before next poll.", poll_interval)
        time.sleep(poll_interval)

    except KeyboardInterrupt:
        log.info("Exiting Modbus bridge...")
        if client.is_socket_open():
            client.close()
        break # Exit the main while loop
    except Exception as e:
        # Catch unexpected errors in the main loop
        log.exception("An unexpected error occurred in the main loop: %s", e) # Log traceback
        if client.is_socket_open():
            client.close()
        log.warning("Waiting 10 seconds before restarting loop due to unexpected error...")
        time.sleep(10)
