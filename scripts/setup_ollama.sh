#!/bin/bash
# Setup Ollama with embedding models for MCP Memoria

set -e

echo "==================================="
echo "  Ollama Setup for MCP Memoria"
echo "==================================="
echo ""

# Check if Ollama is installed
if ! command -v ollama &> /dev/null; then
    echo "Ollama is not installed. Installing..."
    curl -fsSL https://ollama.com/install.sh | sh
fi

# Start Ollama if not running
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "Starting Ollama..."
    ollama serve &
    sleep 5
fi

# Pull embedding models
echo "Pulling embedding models..."

echo "1/3: Pulling nomic-embed-text (recommended, 768d, 8K context)..."
ollama pull nomic-embed-text

echo "2/3: Pulling mxbai-embed-large (high quality, 1024d)..."
ollama pull mxbai-embed-large

echo "3/3: Pulling all-minilm (lightweight, 384d)..."
ollama pull all-minilm

echo ""
echo "==================================="
echo "  Setup Complete!"
echo "==================================="
echo ""
echo "Available embedding models:"
ollama list | grep -E "nomic-embed|mxbai-embed|minilm|bge"
echo ""
echo "Default model: nomic-embed-text"
echo "To change, set MEMORIA_EMBEDDING_MODEL environment variable"
