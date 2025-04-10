
import json
import logging
import sys
import requests
import paho.mqtt.client as mqtt
import os
import ssl
import time
import urllib3 # For disabling SSL warnings

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

http_endpoint = os.getenv("HTTP_ENDPOINT", "https://go-iot-gateway:8080/data")
gateway_api_key = os.getenv("GATEWAY_API_KEY")

mqtt_server_url = os.getenv("MQTT_SERVER", "mqtts://mqtt-broker:8883") # Default to MQTTS
mqtt_topic = os.getenv("MQTT_TOPIC", "sensor/dht11") # Default topic
mqtt_client_id = os.getenv("MQTT_CLIENT_ID", f"mqtt-http-bridge-{os.getpid()}") # Unique client ID

# MQTT Auth & TLS Config
mqtt_user = os.getenv("MQTT_USER")
mqtt_password = os.getenv("MQTT_PASSWORD")
mqtt_ca_cert = os.getenv("MQTT_CA_CERT") # Path to CA cert for TLS verification
mqtt_cert_file = os.getenv("MQTT_CERT_FILE") # Path to client cert (for mTLS)
mqtt_key_file = os.getenv("MQTT_KEY_FILE")   # Path to client key (for mTLS)

# --- Initial Checks ---
if not gateway_api_key:
    log.error("GATEWAY_API_KEY environment variable not set!")
    sys.exit(1)

# Determine MQTT connection details from URL
mqtt_server_host = ""
mqtt_port = 0
use_tls = False

if mqtt_server_url.startswith("mqtts://"):
    use_tls = True
    mqtt_server_host = mqtt_server_url.split("://")[1].split(":")[0]
    try:
        mqtt_port = int(mqtt_server_url.split(":")[-1])
    except (IndexError, ValueError):
        mqtt_port = 8883 # Default MQTTS port
    log.info("Configuring for MQTTS connection to %s:%d", mqtt_server_host, mqtt_port)
elif mqtt_server_url.startswith("mqtt://"):
    use_tls = False
    mqtt_server_host = mqtt_server_url.split("://")[1].split(":")[0]
    try:
        mqtt_port = int(mqtt_server_url.split(":")[-1])
    except (IndexError, ValueError):
        mqtt_port = 1883 # Default MQTT port
    log.info("Configuring for MQTT connection to %s:%d", mqtt_server_host, mqtt_port)
else:
    log.error("Invalid MQTT_SERVER format: %s. Must start with mqtt:// or mqtts://", mqtt_server_url)
    sys.exit(1)

# Determine SSL verification for requests library
verify_ssl = False if "go-iot-gateway" in http_endpoint else True
if not verify_ssl:
    log.warning("SSL verification disabled for Go Gateway endpoint: %s", http_endpoint)
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- MQTT Callbacks ---
def on_connect(client, userdata, flags, reason_code, properties):
    """Callback when client connects to broker."""
    if reason_code == 0:
        log.info("Connected to MQTT broker %s:%d successfully.", mqtt_server_host, mqtt_port)
        # Subscribe to the configured topic
        client.subscribe(mqtt_topic)
        log.info("Subscribed to topic: %s", mqtt_topic)
    else:
        log.error("MQTT Connection failed with reason code %s", reason_code)
        # Consider adding exit logic or retry mechanism here if connection fails

def on_disconnect(client, userdata, flags, reason_code, properties):
    """Callback for disconnection."""
    if reason_code != 0:
        log.warning("Unexpectedly disconnected from MQTT broker with reason code %s. Will attempt to reconnect.", reason_code)
    else:
        log.info("Disconnected from MQTT broker.")
    # Paho library usually handles reconnection automatically if loop_forever is used

def on_message(client, userdata, msg):
    """Callback when message is received on subscribed topic."""
    try:
        payload_str = msg.payload.decode('utf-8')
        log.info("Received MQTT message on topic '%s'", msg.topic)
        log.debug("Payload: %s", payload_str)

        try:
            payload_json = json.loads(payload_str)
            # Add source/topic/device info if needed
            if 'source' not in payload_json:
                payload_json['source'] = 'mqtt'
            if 'topic' not in payload_json:
                payload_json['topic'] = msg.topic
            # Example: Extract device ID from topic like 'sensor/dht11/device123'
            topic_parts = msg.topic.split('/')
            if 'device_id' not in payload_json and len(topic_parts) > 2:
                 payload_json['device_id'] = topic_parts[-1]

        except json.JSONDecodeError:
            log.warning("Received non-JSON MQTT payload: %s. Forwarding as raw value.", payload_str)
            # Wrap non-JSON as a 'value' field
            payload_json = {'value': payload_str, 'source': 'mqtt_raw', 'topic': msg.topic}
            # Potentially extract device ID here too if applicable

        # Send data to HTTP endpoint
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": gateway_api_key,
            "X-Source-Identifier": "mqtt" # Example header
        }

        try:
            log.debug("Forwarding payload to HTTP endpoint: %s", http_endpoint)
            # Ensure verify=verify_ssl is included
            response = requests.post(http_endpoint, headers=headers, json=payload_json, verify=verify_ssl, timeout=10)
            log.info("Forwarded via HTTP, response: %d %s", response.status_code, response.reason)
            # Check for HTTP errors
            if response.status_code == 403:
                 log.error("HTTP Error 403: Forbidden. Check GATEWAY_API_KEY.")
            elif response.status_code == 400:
                 log.error("HTTP Error 400: Bad Request. Check payload format. Response: %s", response.text)
            elif response.status_code >= 500:
                  log.error("HTTP Server Error %d: %s", response.status_code, response.text)

        except requests.exceptions.Timeout:
            log.error("HTTP post timed out to %s", http_endpoint)
        except requests.exceptions.RequestException as e:
            log.error("Error sending data to HTTP endpoint %s: %s", http_endpoint, e)

    except UnicodeDecodeError:
        log.error("Failed to decode MQTT payload as UTF-8. Topic: %s", msg.topic)
    except Exception as e:
        log.exception("Error processing MQTT message: %s", e) # Log traceback

# --- Main Execution ---
if __name__ == "__main__":
    # Initialize MQTT Client (use CallbackAPIVersion.VERSION2 for reason_code)
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=mqtt_client_id)

    # Setup Callbacks
    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect

    # Configure Authentication
    if mqtt_user and mqtt_password:
        client.username_pw_set(mqtt_user, mqtt_password)
        log.info("MQTT username/password configured for user: %s", mqtt_user)

    # Configure TLS if needed
    if use_tls:
        log.info("Configuring MQTT TLS...")
        tls_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        # Load CA cert if provided to verify broker certificate
        if mqtt_ca_cert:
            try:
                tls_context.load_verify_locations(cafile=mqtt_ca_cert)
                log.info("Loaded CA certificate for broker verification: %s", mqtt_ca_cert)
                tls_context.verify_mode = ssl.CERT_REQUIRED # Verify broker cert against CA
                tls_context.check_hostname = True
            except FileNotFoundError:
                 log.error("MQTT CA certificate file not found: %s", mqtt_ca_cert)
                 sys.exit(1)
            except Exception as e:
                 log.error("Error loading MQTT CA certificate: %s", e)
                 sys.exit(1)
        else:
            # Allow connection without verifying server cert (less secure)
            log.warning("MQTT_CA_CERT not specified, TLS connection to broker will be unverified.")
            tls_context.check_hostname = False
            tls_context.verify_mode = ssl.CERT_NONE

        # Load client certificate/key if provided (for mutual TLS)
        if mqtt_cert_file and mqtt_key_file:
            try:
                log.info("Loading client certificate: %s and key: %s for mTLS", mqtt_cert_file, mqtt_key_file)
                tls_context.load_cert_chain(certfile=mqtt_cert_file, keyfile=mqtt_key_file)
            except FileNotFoundError:
                log.error("Client cert or key file not found: %s / %s", mqtt_cert_file, mqtt_key_file)
                sys.exit(1)
            except Exception as e:
                 log.error("Error loading client certificate/key: %s", e)
                 sys.exit(1)
        elif mqtt_cert_file or mqtt_key_file:
             log.warning("MQTT_CERT_FILE or MQTT_KEY_FILE specified, but not both. Client certificate not loaded.")

        # Apply TLS settings to the client
        client.tls_set_context(tls_context)
        # For debugging TLS issues ONLY (VERY insecure for production):
        # client.tls_insecure_set(True)


    # Connect to MQTT Broker
    try:
        log.info("Connecting to MQTT broker at %s:%d...", mqtt_server_host, mqtt_port)
        client.connect(mqtt_server_host, mqtt_port, 60) # 60 second keepalive
    except ssl.SSLError as e:
         log.error("MQTT TLS/SSL Connection Error: %s. Check certificates and TLS configuration on broker/client.", e)
         sys.exit(1)
    except ConnectionRefusedError as e:
         log.error("MQTT Connection Refused: %s. Check broker address, port, firewall, and authentication settings.", e)
         sys.exit(1)
    except Exception as e:
        log.exception("Failed to connect to MQTT broker: %s", e) # Log traceback
        sys.exit(1)

    # Start the Network Loop (Blocking)
    try:
        log.info("Starting MQTT network loop...")
        client.loop_forever()
    except KeyboardInterrupt:
        log.info("Disconnecting from MQTT broker...")
        client.disconnect()
        log.info("Exiting.")
    except Exception as e:
         log.exception("Error during MQTT loop: %s", e) # Log traceback
         client.disconnect() # Attempt graceful disconnect on error
         sys.exit(1) # Exit on loop error
