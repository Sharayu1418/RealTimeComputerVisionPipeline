FROM python:3.11-slim
WORKDIR /app
COPY services/tracker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY common/ ./common/
COPY services/tracker/ .
ENV PYTHONPATH=/app
CMD ["python", "main.py"]
