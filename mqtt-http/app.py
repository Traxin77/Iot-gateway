import json
import logging
import sys
import requests
import paho.mqtt.client as mqtt
import os
import ssl
# Load Configuration
#with open("config.json") as cfg_file:
#    cfg = json.load(cfg_file)

#loglevel = sys.argv[1] if len(sys.argv) > 1 else "INFO"
#numeric_level = getattr(logging, loglevel.upper(), None)
#if not isinstance(numeric_level, int):
#    raise ValueError(f"Invalid log level: {loglevel}")
#logging.basicConfig(level=numeric_level)
mqtt_server = os.getenv("MQTT_SERVER", "mqtt-broker") # Default hostname
mqtt_port = int(os.getenv("MQTT_PORT", "1883")) # Default port
mqtt_topic = os.getenv("MQTT_TOPIC", "sensor/dht11")
http_endpoint = os.getenv("HTTP_ENDPOINT", "http://go-iot-gateway:8080/data")
mqtt_user = os.getenv("MQTT_USER") # Optional username
mqtt_password = os.getenv("MQTT_PASSWORD") # Optional password
mqtt_ca_cert = os.getenv("MQTT_CA_CERT") # Path to CA cert for TLS verification
gateway_api_key = os.getenv("GATEWAY_API_KEY") # API Key for Go Gateway

if not gateway_api_key:
    logging.error("GATEWAY_API_KEY environment variable not set!")
    sys.exit(1)

# MQTT Callbacks
def on_connect(client, userdata, flags, reason_code, properties):
    """Callback when client connects to broker."""
    if reason_code == 0:
        logging.info("Connected to MQTT broker successfully.")
        client.subscribe(cfg['mqtt_topic'])
    else:
        logging.error(f"Connection failed with reason code {reason_code}")

def on_disconnect(client, userdata, flags, reason_code, properties):
    """Callback for disconnection."""
    logging.warning(f"Disconnected from MQTT broker with reason code {reason_code}")

def on_message(client, userdata, msg):
    """Callback when message is received on subscribed topic."""
    try:
        payload = msg.payload.decode()
        logging.debug(f"Received MQTT message: {payload}")

        # Send data to HTTP endpoint
        headers = {
            "Content-Type": "application/json"
            "X-API-Key": gateway_api_key
        }
        verify_ssl = False if "go-iot-gateway" in http_endpoint else True
        logging.info(f"Sent to HTTP endpoint {http_endpoint}: {payload[:50]}...") # Log truncated payload
        logging.debug(f"Response: {response.status_code} - {response.text}")
    except json.JSONDecodeError:
         logging.error(f"Error decoding MQTT payload to JSON: {payload}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Error sending data to HTTP endpoint {http_endpoint}: {e}")
    except Exception as e:
        logging.error(f"Error processing message: {e}")

# Initialize MQTT Client
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

# Setup Callbacks
client.on_connect = on_connect
client.on_message = on_message
client.on_disconnect = on_disconnect

# --> Configure Authentication <--
if mqtt_user and mqtt_password:
    client.username_pw_set(mqtt_user, mqtt_password)
    logging.info("MQTT username/password configured.")

if mqtt_port == 8883 or (mqtt_ca_cert): # Common TLS port or if CA cert specified
    logging.info("Configuring MQTT TLS...")
    tls_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    if mqtt_ca_cert:
        try:
            tls_context.load_verify_locations(cafile=mqtt_ca_cert)
            logging.info(f"Loaded CA certificate: {mqtt_ca_cert}")
            client.tls_set_context(tls_context)
        except FileNotFoundError:
            logging.error(f"MQTT CA certificate file not found: {mqtt_ca_cert}")
            sys.exit(1)
        except Exception as e:
            logging.error(f"Error loading MQTT CA certificate: {e}")
            sys.exit(1)
    else:
        # Allow connection without verifying server cert (less secure, use with caution)
        logging.warning("MQTT_CA_CERT not specified, TLS connection will be unverified.")
        client.tls_set_context(tls_context)    
try:
    client.connect(mqtt_server, mqtt_port, 60)
    logging.info(f"Connecting to MQTT broker at {mqtt_server}:{mqtt_port}...")
except ssl.SSLError as e:
     logging.error(f"MQTT TLS/SSL Error: {e}. Check certificates and TLS configuration.")
     sys.exit(1)
except Exception as e:
    logging.error(f"Failed to connect to MQTT broker: {e}")
    sys.exit(1)

# Start the Loop
try:
    client.loop_forever()
except KeyboardInterrupt:
    logging.info("Disconnecting from MQTT broker...")
    client.disconnect()
    logging.info("Exiting.")

