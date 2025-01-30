FROM python:3.11

WORKDIR /app

COPY requirements.txt ./
COPY bot.py ./

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "bot.py"]
