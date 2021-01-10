FROM python:3
ENV PYTHONUNBUFFERED=1
WORKDIR /code
COPY ./src /code
RUN pip install -r requirements.txt
CMD ["python", "main.py"]
