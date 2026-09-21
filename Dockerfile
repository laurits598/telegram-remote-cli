FROM python:3.12-slim

WORKDIR /app

COPY bot.py agent.py ./

CMD ["python", "bot.py"]
