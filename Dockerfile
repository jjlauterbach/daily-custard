FROM python:3.12
 
WORKDIR /code

# Install Chromium and ChromeDriver (works on both amd64 and arm64)
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables for Selenium to find Chromium
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver
 
COPY ./pyproject.toml /code/pyproject.toml

RUN pip install --no-cache-dir --upgrade pip && pip install .[dev]
 
COPY ./app /code/app
COPY ./static /code/static
 
CMD ["uvicorn", "app.main:app", "--proxy-headers", "--host", "0.0.0.0", "--port", "80"]
