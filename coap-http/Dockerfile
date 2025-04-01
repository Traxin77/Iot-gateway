FROM python:3.10
WORKDIR /app
COPY coap-server.py /app/
RUN pip install aiocoap requests
EXPOSE 5683/udp
CMD ["python", "coap-server.py"]

