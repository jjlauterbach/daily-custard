FROM python:3.12
 
WORKDIR /code

# Install Chromium and ChromeDriver (works on both amd64 and arm64)
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

COPY ./pyproject.toml /code/pyproject.toml

RUN pip install --no-cache-dir --upgrade pip && pip install .[dev]
 
COPY ./app /code/app
COPY ./static /code/static

# Serve static files with Python's built-in server
EXPOSE 8000
CMD ["python", "-m", "http.server", "--directory", "/code/static", "8000"]
