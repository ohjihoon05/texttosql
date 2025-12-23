FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install DuckDB excel extension
RUN python -c "import duckdb; duckdb.connect().execute('INSTALL excel; LOAD excel;')"

# Copy application code
COPY src/ ./src/
COPY data/ ./data/
COPY scripts/ ./scripts/

# Expose Chainlit port
EXPOSE 3000

# Run Chainlit
CMD ["chainlit", "run", "src/main.py", "--host", "0.0.0.0", "--port", "3000"]
