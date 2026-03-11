# Use official Python image based on Ubuntu
FROM python:3.9

# Set environment variables for GDAL (Keep these, they are good)
ENV CPLUS_INCLUDE_PATH=/usr/include/gdal
ENV C_INCLUDE_PATH=/usr/include/gdal

# Install GDAL and dependencies
RUN apt-get update && apt-get install -y \
    gdal-bin \
    libpq-dev \
    libgdal-dev \
    python3-gdal \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt
# Install Gunicorn explicitly (ensure it's available)
RUN pip install gunicorn

# Copy project files
COPY . .

# Run the app using Gunicorn (Production Server)
# -w 3: Runs 3 worker processes (good for handling concurrent requests)
# -b 0.0.0.0:5000: Binds to port 5000
CMD ["gunicorn", "-w", "3", "-b", "0.0.0.0:5000", "app:app"]
