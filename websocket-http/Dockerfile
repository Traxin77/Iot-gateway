FROM python:3.10
WORKDIR /app
COPY websocket_server.py /app/
RUN pip install pymodbus websockets requests
EXPOSE 5000
CMD ["python", "websocket_server.py"]

