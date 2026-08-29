FROM python:3.11-slim

# Install docker.io to enable Docker-in-Docker socket usage for sandbox
RUN apt-get update && apt-get install -y docker.io && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy all necessary backend code and modules
COPY backend/ ./backend/
COPY tools/ ./tools/
COPY security/ ./security/
COPY postgre/ ./postgre/
COPY model/ ./model/

# Expose port and run
EXPOSE 8000
CMD ["gunicorn", "backend.main:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8000"]
