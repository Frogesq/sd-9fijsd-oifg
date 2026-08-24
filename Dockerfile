FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Install watchdog for hot-reloading
RUN pip install --no-cache-dir watchdog[watchmedo]

COPY . .

# Default command (will be overridden by docker-compose for dev)
CMD ["python", "main.py"]
