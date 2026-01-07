#!/bin/bash
# MCP Memoria Installation Script

set -e

echo "==================================="
echo "  MCP Memoria Installation"
echo "==================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check Python version
check_python() {
    echo -n "Checking Python... "
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
        if [[ $(echo "$PYTHON_VERSION >= 3.11" | bc -l) -eq 1 ]]; then
            echo -e "${GREEN}OK${NC} (Python $PYTHON_VERSION)"
            return 0
        fi
    fi
    echo -e "${RED}FAILED${NC}"
    echo "Python 3.11+ is required. Please install it first."
    exit 1
}

# Check if Ollama is installed
check_ollama() {
    echo -n "Checking Ollama... "
    if command -v ollama &> /dev/null; then
        echo -e "${GREEN}OK${NC}"
        return 0
    else
        echo -e "${YELLOW}NOT FOUND${NC}"
        echo ""
        read -p "Would you like to install Ollama? [y/N] " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            install_ollama
        else
            echo "Please install Ollama manually: https://ollama.com/download"
            exit 1
        fi
    fi
}

# Install Ollama
install_ollama() {
    echo "Installing Ollama..."
    curl -fsSL https://ollama.com/install.sh | sh
    echo -e "${GREEN}Ollama installed${NC}"
}

# Check if Ollama is running
check_ollama_running() {
    echo -n "Checking if Ollama is running... "
    if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo -e "${GREEN}OK${NC}"
        return 0
    else
        echo -e "${YELLOW}NOT RUNNING${NC}"
        echo "Starting Ollama..."
        ollama serve &
        sleep 3
        if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
            echo -e "${GREEN}Ollama started${NC}"
        else
            echo -e "${RED}Failed to start Ollama${NC}"
            exit 1
        fi
    fi
}

# Pull embedding model
pull_embedding_model() {
    echo -n "Pulling nomic-embed-text model... "
    if ollama list | grep -q "nomic-embed-text"; then
        echo -e "${GREEN}ALREADY INSTALLED${NC}"
    else
        ollama pull nomic-embed-text
        echo -e "${GREEN}OK${NC}"
    fi
}

# Install Python package
install_package() {
    echo "Installing MCP Memoria..."

    # Get script directory
    SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
    PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

    cd "$PROJECT_DIR"

    # Create virtual environment if not exists
    if [ ! -d "venv" ]; then
        echo "Creating virtual environment..."
        python3 -m venv venv
    fi

    # Activate and install
    source venv/bin/activate
    pip install --upgrade pip
    pip install -e ".[dev]"

    echo -e "${GREEN}Package installed${NC}"
}

# Create config directories
create_directories() {
    echo "Creating data directories..."
    mkdir -p ~/.mcp-memoria/qdrant
    mkdir -p ~/.mcp-memoria/cache
    echo -e "${GREEN}OK${NC}"
}

# Configure Claude Code
configure_claude_code() {
    echo ""
    echo "==================================="
    echo "  Claude Code Configuration"
    echo "==================================="
    echo ""

    CONFIG_DIR="$HOME/.claude"
    CONFIG_FILE="$CONFIG_DIR/config.json"

    # Get absolute path to Python
    SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
    PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
    PYTHON_PATH="$PROJECT_DIR/venv/bin/python"

    MCP_CONFIG=$(cat <<EOF
{
  "mcp_servers": {
    "memoria": {
      "command": "$PYTHON_PATH",
      "args": ["-m", "mcp_memoria"],
      "env": {
        "MEMORIA_QDRANT_PATH": "$HOME/.mcp-memoria/qdrant",
        "MEMORIA_CACHE_PATH": "$HOME/.mcp-memoria/cache",
        "MEMORIA_OLLAMA_HOST": "http://localhost:11434",
        "MEMORIA_EMBEDDING_MODEL": "nomic-embed-text",
        "MEMORIA_LOG_LEVEL": "INFO"
      }
    }
  }
}
EOF
)

    echo "Add the following to your Claude Code configuration:"
    echo ""
    echo "$MCP_CONFIG"
    echo ""
    echo "Configuration file location: $CONFIG_FILE"
    echo ""

    read -p "Would you like to automatically add this configuration? [y/N] " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        mkdir -p "$CONFIG_DIR"

        if [ -f "$CONFIG_FILE" ]; then
            echo "Backing up existing config to $CONFIG_FILE.backup"
            cp "$CONFIG_FILE" "$CONFIG_FILE.backup"
            echo -e "${YELLOW}Please manually merge the memoria configuration${NC}"
        else
            echo "$MCP_CONFIG" > "$CONFIG_FILE"
            echo -e "${GREEN}Configuration saved${NC}"
        fi
    fi
}

# Main installation flow
main() {
    check_python
    check_ollama
    check_ollama_running
    pull_embedding_model
    install_package
    create_directories
    configure_claude_code

    echo ""
    echo "==================================="
    echo -e "  ${GREEN}Installation Complete!${NC}"
    echo "==================================="
    echo ""
    echo "To use MCP Memoria:"
    echo "1. Restart Claude Code"
    echo "2. The memoria tools will be available automatically"
    echo ""
    echo "Available tools:"
    echo "  - memoria_store: Store new memories"
    echo "  - memoria_recall: Recall relevant memories"
    echo "  - memoria_search: Advanced search"
    echo "  - memoria_stats: View statistics"
    echo ""
    echo "For Docker deployment, see: docker/docker-compose.yml"
    echo ""
}

main "$@"
