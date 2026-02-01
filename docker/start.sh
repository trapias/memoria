#!/bin/bash

# Memoria Docker Quick Start Script
# Usage:
#   ./start.sh              # Start with default settings
#   ./start.sh central      # Start central architecture (Qdrant + PostgreSQL)
#   ./start.sh http         # Start HTTP/SSE transport
#   ./start.sh qdrant-only  # Start Qdrant only
#   ./start.sh stop         # Stop all services
#   ./start.sh clean        # Remove all containers and volumes

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Functions
print_header() {
    echo -e "${BLUE}=== Memoria Docker Setup ===${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
    exit 1
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

check_docker() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed or not in PATH"
    fi
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose is not installed or not in PATH"
    fi
    print_success "Docker and Docker Compose found"
}

load_env() {
    if [ -f .env ]; then
        print_info "Loading .env file"
        export $(cat .env | grep -v '^#' | xargs)
    else
        print_warning ".env file not found, using defaults"
        print_info "Copy .env.example to .env to customize"
    fi
}

start_central() {
    print_header
    print_info "Starting Central Architecture (Qdrant + PostgreSQL)"

    check_docker
    load_env

    print_info "Services to start:"
    echo "  - Qdrant (vector database) on :6333/:6334"
    echo "  - PostgreSQL (relational database) on :5432"

    print_info "Starting services..."
    docker-compose -f docker-compose.central.yml up -d

    print_success "Services started"

    print_info "Waiting for services to be healthy..."
    sleep 5

    # Check health
    if docker-compose -f docker-compose.central.yml ps | grep -q "healthy"; then
        print_success "All services are healthy"
    else
        print_warning "Services may still be starting, check with: docker-compose -f docker-compose.central.yml ps"
    fi

    print_info "Connection strings:"
    echo "  Qdrant: http://localhost:6333"
    echo "  PostgreSQL: postgresql://memoria:${POSTGRES_PASSWORD:-memoria_dev}@localhost:5432/memoria"

    echo ""
    print_success "Setup complete!"
}

start_http() {
    print_header
    print_info "Starting HTTP/SSE Transport"

    check_docker
    load_env

    print_info "Services to start:"
    echo "  - Qdrant (vector database) on :6333/:6334"
    echo "  - Memoria HTTP server on :8765"

    print_info "Starting services..."
    docker-compose -f docker-compose.http.yml up -d

    print_success "Services started"

    print_info "Waiting for services to be healthy..."
    sleep 5

    # Check health
    if docker-compose -f docker-compose.http.yml ps | grep -q "healthy"; then
        print_success "All services are healthy"
    else
        print_warning "Services may still be starting, check with: docker-compose -f docker-compose.http.yml ps"
    fi

    print_info "Memoria is accessible at: http://localhost:8765/sse"
    print_info "Add to Claude Code config (~/.claude/config.json):"
    cat << 'EOF'

{
  "mcp_servers": {
    "memoria": {
      "url": "http://localhost:8765/sse"
    }
  }
}
EOF

    echo ""
    print_success "Setup complete!"
}

start_qdrant_only() {
    print_header
    print_info "Starting Qdrant Only"

    check_docker
    load_env

    print_info "Services to start:"
    echo "  - Qdrant (vector database) on :6333/:6334"

    print_info "Starting services..."
    docker-compose -f docker-compose.qdrant-only.yml up -d

    print_success "Services started"

    print_info "Waiting for services to be healthy..."
    sleep 5

    # Check health
    if docker-compose -f docker-compose.qdrant-only.yml ps | grep -q "healthy"; then
        print_success "All services are healthy"
    else
        print_warning "Services may still be starting, check with: docker-compose -f docker-compose.qdrant-only.yml ps"
    fi

    print_info "Qdrant is accessible at: http://localhost:6333"
    print_info "Run local MCP server with: python -m mcp_memoria"

    echo ""
    print_success "Setup complete!"
}

stop_services() {
    print_header
    print_info "Stopping all services"

    check_docker

    # Try to stop from all configs
    docker-compose -f docker-compose.central.yml down 2>/dev/null || true
    docker-compose -f docker-compose.http.yml down 2>/dev/null || true
    docker-compose -f docker-compose.qdrant-only.yml down 2>/dev/null || true

    print_success "All services stopped"
}

clean_all() {
    print_header
    print_warning "This will remove all containers and volumes!"
    echo -n "Are you sure? (y/N) "
    read -r response

    if [ "$response" != "y" ] && [ "$response" != "Y" ]; then
        print_info "Cancelled"
        exit 0
    fi

    check_docker

    print_info "Removing containers and volumes..."

    # Remove from all configs
    docker-compose -f docker-compose.central.yml down -v 2>/dev/null || true
    docker-compose -f docker-compose.http.yml down -v 2>/dev/null || true
    docker-compose -f docker-compose.qdrant-only.yml down -v 2>/dev/null || true

    print_success "All containers and volumes removed"
}

show_status() {
    print_header
    print_info "Service Status"
    echo ""

    check_docker

    echo -e "${BLUE}Central Architecture:${NC}"
    docker-compose -f docker-compose.central.yml ps 2>/dev/null || echo "  Not running"
    echo ""

    echo -e "${BLUE}HTTP/SSE Transport:${NC}"
    docker-compose -f docker-compose.http.yml ps 2>/dev/null || echo "  Not running"
    echo ""

    echo -e "${BLUE}Qdrant Only:${NC}"
    docker-compose -f docker-compose.qdrant-only.yml ps 2>/dev/null || echo "  Not running"
}

show_logs() {
    if [ -z "$1" ]; then
        echo "Usage: ./start.sh logs [central|http|qdrant-only] [service]"
        exit 1
    fi

    case "$1" in
        central)
            docker-compose -f docker-compose.central.yml logs -f ${2:-}
            ;;
        http)
            docker-compose -f docker-compose.http.yml logs -f ${2:-}
            ;;
        qdrant-only)
            docker-compose -f docker-compose.qdrant-only.yml logs -f ${2:-}
            ;;
        *)
            print_error "Unknown config: $1"
            ;;
    esac
}

# Main
case "${1:-central}" in
    central)
        start_central
        ;;
    http)
        start_http
        ;;
    qdrant-only)
        start_qdrant_only
        ;;
    stop)
        stop_services
        ;;
    clean)
        clean_all
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs "$2" "$3"
        ;;
    *)
        cat << EOF
${BLUE}Memoria Docker Quick Start${NC}

Usage:
  ./start.sh [COMMAND]

Commands:
  central         Start central architecture (Qdrant + PostgreSQL) [default]
  http            Start HTTP/SSE transport with Qdrant
  qdrant-only     Start Qdrant only (minimal setup)
  stop            Stop all services
  clean           Remove all containers and volumes
  status          Show service status
  logs [TYPE]     Show logs (central|http|qdrant-only) [service]

Examples:
  ./start.sh                    # Start central architecture
  ./start.sh http               # Start HTTP transport
  ./start.sh stop               # Stop all services
  ./start.sh logs central       # View central logs
  ./start.sh logs http memoria  # View memoria logs

Environment:
  Create a .env file from .env.example to customize settings
  Example: cp .env.example .env && nano .env

Documentation:
  See README.md for detailed configuration and troubleshooting
EOF
        ;;
esac
