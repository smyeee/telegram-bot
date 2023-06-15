FROM python:3.10.6

WORKDIR /bot

RUN pip install poetry

COPY . .

RUN poetry install

CMD ["python", "main.py"]

