# Multi-architecture Python image (supports ARM64 for Raspberry Pi)
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables for Python optimization
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies (minimal for ARM/Pi)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        libc6-dev \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && rm -rf ~/.cache/pip

# Copy application code
COPY eq_crafting_bot.py .
COPY health_check.py .

# Create logs directory with proper permissions
RUN mkdir -p logs && chmod 755 logs

# Create non-root user for security (important for Pi)
RUN groupadd -r eqbot && useradd -r -g eqbot -d /app -s /bin/bash eqbot \
    && chown -R eqbot:eqbot /app

# Switch to non-root user
USER eqbot

# Simple health check optimized for Pi resources
HEALTHCHECK --interval=120s --timeout=15s --start-period=30s --retries=2 \
    CMD python health_check.py --check pid --quiet || exit 1

# Run the bot
CMD ["python", "eq_crafting_bot.py"]