FROM python:3.9-alpine

RUN apk add --no-cache git

RUN pip install --no-cache-dir Flask==1.1.1

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "app.py"]
