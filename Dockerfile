FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY core/ core/
COPY provider.py config.py main.py ./

VOLUME /app/data

ENV ACCOUNTS_DIR=/app/data
ENV HOST=0.0.0.0
ENV PORT=9090

EXPOSE 9090

CMD ["python", "main.py"]
