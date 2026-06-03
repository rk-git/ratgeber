#!/bin/bash
set -e

# Start Ollama daemon in background
ollama serve &
OLLAMA_PID=$!

# Wait for Ollama to be ready
echo "Waiting for Ollama to start..."
until ollama list > /dev/null 2>&1; do
    sleep 1
done
echo "Ollama is ready."

# Pull mistral if not already present
if ! ollama list | grep -q "mistral"; then
    echo "Pulling mistral model (first run — this will take a while)..."
    ollama pull mistral
fi

# Start Ratgeber
exec python -m src.ui.cli "$@"
