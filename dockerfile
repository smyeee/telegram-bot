FROM python:3.10.6-slim

RUN apt-get update \
    && apt-get install -y wkhtmltopdf \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /bot

COPY requirements.txt .

RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .

# RUN python3 -u main.py