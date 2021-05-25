FROM python:3

ENV PYTHONUNBUFFERED=1

RUN DEBIAN_FRONTEND=noninteractive \
    apt-get update && \
    apt-get install -y ffmpeg libffi-dev libnacl-dev python3-dev

# Install requirements first to take advantage of docker build layer caching
COPY ./src/requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt && rm /tmp/requirements.txt

COPY ./src /code

WORKDIR /code
ENTRYPOINT ["python", "./main.py"]
