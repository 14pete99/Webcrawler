FROM python:3.12-slim

WORKDIR /app

# Install dependencies first (layer caching)
COPY pyproject.toml .
RUN pip install --no-cache-dir . && pip install --no-cache-dir .

# Copy application code
COPY . .

# Re-install so the app package is available
RUN pip install --no-cache-dir -e .

EXPOSE 8000

# Default: run the FastAPI API server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
