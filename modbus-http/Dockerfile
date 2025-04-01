FROM python:3.10
WORKDIR /app
COPY modbus_client.py /app/
RUN pip install pymodbus requests
CMD ["python", "modbus_client.py"]

