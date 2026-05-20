FROM python:3.14-slim

# Copy application files
WORKDIR /app
COPY flairtimermodbot.py .
COPY update_checker.py .
COPY requirements.txt .

RUN mkdir -p /app/config

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt 

ENV PYTHONUNBUFFERED=1

# Run the script
CMD ["python", "flairtimermodbot.py"]
