FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Railway persistent volume mount point
VOLUME [ "/data" ]

# Run with hypercorn, bind to $PORT
CMD ["hypercorn", "src.main:app", "--bind", "0.0.0.0:$PORT"]
