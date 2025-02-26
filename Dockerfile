# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Install required OS packages for Playwright and building C extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential \
      python3-dev \
      libnss3 \
      libatk1.0-0 \
      libatk-bridge2.0-0 \
      libcups2 \
      libxkbcommon-x11-0 \
      libgbm-dev \
      libpango1.0-0 \
      libxcomposite1 \
      libxrandr2 \
      libasound2 \
      libpangocairo-1.0-0 \
      libatspi2.0-0 \
      libgtk-3-0 \
      libxdamage1 \
      libxshmfence1 \
      libx11-xcb1 \
      libxcb-dri3-0 \
      libdrm2 \
      && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Copy only requirements.txt first for better caching
COPY requirements.txt .

# Upgrade pip and install dependencies
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install

# Copy the rest of the app
COPY . .

# Make port 5000 available
EXPOSE 5000

# Run Uvicorn to serve the FastAPI app
CMD ["uvicorn", "app:app_api", "--host", "0.0.0.0", "--port", "5000", "--log-level", "info"]