import json
import logging
import sys
import requests
import paho.mqtt.client as mqtt

# Load Configuration
with open("config.json") as cfg_file:
    cfg = json.load(cfg_file)

# Setup Logging
loglevel = sys.argv[1] if len(sys.argv) > 1 else "INFO"
numeric_level = getattr(logging, loglevel.upper(), None)
if not isinstance(numeric_level, int):
    raise ValueError(f"Invalid log level: {loglevel}")
logging.basicConfig(level=numeric_level)

# MQTT Callbacks
def on_connect(client, userdata, flags, reason_code, properties):
    """Callback when client connects to broker."""
    if reason_code == 0:
        logging.info("Connected to MQTT broker successfully.")
        client.subscribe(cfg['mqtt_topic'])
    else:
        logging.error(f"Connection failed with reason code {reason_code}")

def on_message(client, userdata, msg):
    """Callback when message is received on subscribed topic."""
    try:
        payload = msg.payload.decode()
        logging.debug(f"Received MQTT message: {payload}")

        # Send data to HTTP endpoint
        headers = {"Content-Type": "application/json"}
        http_endpoint = os.getenv("HTTP_ENDPOINT", cfg["http_endpoint"])
        response = requests.post(cfg['http_endpoint'], data=payload, headers=headers)

        logging.info(f"Sent to HTTP: {payload}")
        logging.debug(f"Response: {response.status_code} - {response.text}")
    except Exception as e:
        logging.error(f"Error processing message: {e}")

# Initialize MQTT Client
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

# Setup Callbacks
client.on_connect = on_connect
client.on_message = on_message

# Connect to MQTT Broker
try:
    client.connect(cfg['mqtt_server'], 1883, 60)
    logging.info("Connecting to MQTT broker...")
except Exception as e:
    logging.error(f"Failed to connect to MQTT broker: {e}")
    sys.exit(1)

# Start the Loop
client.loop_forever()

