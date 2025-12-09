# Use Python with Playwright dependencies pre-installed
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
ENV PORT=8080

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright (already has browsers from base image, but ensure Python package)
RUN pip install playwright==1.40.0

# Copy application code
COPY . .

# Create output directory
RUN mkdir -p /app/output/images /app/output/extractions

# Expose port
EXPOSE 8080

# Use shell form so $PORT gets expanded
CMD gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120
