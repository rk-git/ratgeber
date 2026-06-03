FROM python:3.13-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Ollama
RUN curl -fsSL https://ollama.com/install.sh | sh

# Python dependencies
COPY requirements-docker.txt .
RUN pip install --no-cache-dir -r requirements-docker.txt

# Download spaCy models (English + German)
RUN python -m spacy download en_core_web_sm && \
    python -m spacy download de_core_news_sm

# Copy source
COPY src/ ./src/

# Volumes for persistence
VOLUME ["/root/.ollama", "/app/data/chroma_db"]

COPY docker/docker-entrypoint.sh .
RUN chmod +x docker-entrypoint.sh
ENTRYPOINT ["./docker-entrypoint.sh"]
