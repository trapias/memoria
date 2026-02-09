#!/bin/bash
# Update MCP Memoria to the latest version
# Usage: ./scripts/update.sh

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=== MCP Memoria Update ===${NC}"

# Detect if inside Docker
if [ -f /.dockerenv ] || [ "$MEMORIA_RUNNING_IN_DOCKER" = "true" ]; then
    echo -e "${RED}Running inside Docker. To update, run from the host:${NC}"
    echo "  docker compose pull && docker compose up -d"
    exit 1
fi

# Detect install method
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

if [ -d "$SCRIPT_DIR/.git" ]; then
    echo -e "${BLUE}Detected git clone installation${NC}"
    echo "Pulling latest changes..."
    cd "$SCRIPT_DIR"
    git pull
    echo "Installing updated package..."
    pip install -e .
else
    echo -e "${BLUE}Updating from GitHub...${NC}"
    pip install --upgrade git+https://github.com/trapias/memoria.git
fi

echo -e "${GREEN}Update complete!${NC}"
echo "Restart your MCP client to use the new version."
