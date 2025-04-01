from pymodbus.client import ModbusTcpClient
import requests
import time
import os
modbus_ip = '192.168.141.173'  # ESP8266 IP address
modbus_port = 1502  # or try 5020 / 8502 if still filtered

http_endpoint = os.getenv("HTTP_ENDPOINT", "http://go-iot-gateway:8080/data")

client = ModbusTcpClient(modbus_ip, port=modbus_port, timeout=5) # Increased timeout

retry_interval = 2  # seconds
max_retries = 5

while True:
    try:
        if not client.is_socket_open():
            retries = 0
            while retries < max_retries:
                print(f"Attempting to connect to Modbus server at {modbus_ip}:{modbus_port}, attempt {retries + 1}/{max_retries}")
                try:
                    client.connect()
                    if client.is_socket_open():
                        print("Successfully connected to Modbus server.")
                        break
                except Exception as e:
                    print(f"Connection error: {e}")
                retries += 1
                time.sleep(retry_interval)
            if not client.is_socket_open():
                print(f"Could not connect to Modbus server after {max_retries} retries.")
                time.sleep(5)
                continue

        try:
            rr = client.read_holding_registers(address=1, count=2)
            if rr.isError():
                print(f"Modbus read error: {rr}")
            else:
                temp = rr.registers[0] / 10.0
                hum = rr.registers[1] / 10.0
                print(f"Temp: {temp} °C, Hum: {hum} %")

                payload = {'temperature': temp, 'humidity': hum}
                try:
                    response = requests.post(http_endpoint, json=payload)
                    print("Posted to HTTP:", response.status_code)
                except requests.exceptions.RequestException as e:
                    print("HTTP post error:", e)

        except Exception as e:
            print(f"Error during Modbus communication: {e}")
            if client.is_socket_open():
                client.close()

        time.sleep(5)

    except KeyboardInterrupt:
        print("Exiting...")
        if client.is_socket_open():
            client.close()
        break
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        if client.is_socket_open():
            client.close()
        time.sleep(5)

