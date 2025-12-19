# Use an official Python base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt


COPY .env .env
COPY busmon.py .
COPY templates/ templates/

# Expose port
EXPOSE 8005

# Run the app
CMD ["python", "busmon.py"]
