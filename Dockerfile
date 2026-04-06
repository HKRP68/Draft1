FROM python:3.11-slim

# Install wkhtmltopdf for imgkit
RUN apt-get update && \
    apt-get install -y --no-install-recommends wkhtmltopdf && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY cricket-bot/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY cricket-bot/ .

# Create logs directory
RUN mkdir -p logs

CMD ["python", "main.py"]
