FROM alpine:latest

ENV PYTHONUNBUFFERED=1

RUN apk add --no-cache \
    python3 \
    py3-pip \
    py3-virtualenv

WORKDIR /app

COPY requirements.txt .
RUN python3 -m venv venv && \
    ./venv/bin/pip install --no-cache-dir -r requirements.txt

COPY ./check_env.py .

CMD ["sh", "-c", "./venv/bin/python3 check_env.py $ARGS"]
