FROM python:3.10.4

WORKDIR /bot

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "-m", "watchdog", "main.py"]

