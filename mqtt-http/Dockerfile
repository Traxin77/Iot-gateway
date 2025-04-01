FROM python:3.10
WORKDIR /app
COPY app.py config.json /app/
RUN pip install paho-mqtt requests
CMD ["python", "app.py"]

