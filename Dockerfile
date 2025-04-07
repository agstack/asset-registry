# Use official Python image based on Ubuntu
FROM python:3.9

# Set environment variables for GDAL
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
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Expose port (if needed)
#EXPOSE 80

# Run the app
CMD ["python", "app.py"]
