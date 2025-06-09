#!/bin/bash

# EverQuest Forum Crafting Bot - Raspberry Pi Deployment Script
# Optimized for Raspberry Pi with Docker Compose

set -e  # Exit on any error

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.yml"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1" >&2
}

warn() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1"
}

info() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')] INFO:${NC} $1"
}

# Check if running on Raspberry Pi
check_raspberry_pi() {
    log "Checking Raspberry Pi environment..."
    
    if [ ! -f /proc/device-tree/model ]; then
        warn "Cannot detect Pi model. Continuing anyway..."
        return 0
    fi
    
    local pi_model=$(cat /proc/device-tree/model 2>/dev/null | tr -d '\0')
    if [[ "$pi_model" == *"Raspberry Pi"* ]]; then
        log "Detected: $pi_model ✓"
        
        # Check architecture
        local arch=$(uname -m)
        case $arch in
            armv7l|aarch64|arm64)
                log "Architecture: $arch (ARM compatible) ✓"
                ;;
            *)
                warn "Unexpected architecture: $arch"
                ;;
        esac
    else
        warn "Not running on Raspberry Pi, but continuing deployment..."
    fi
}

# Check system resources
check_system_resources() {
    log "Checking system resources..."
    
    # Check available memory
    local mem_total=$(grep MemTotal /proc/meminfo | awk '{print $2}')
    local mem_gb=$((mem_total / 1024 / 1024))
    
    if [ $mem_gb -lt 1 ]; then
        warn "Low memory detected: ${mem_gb}GB. Bot may run slowly."
    else
        log "Memory: ${mem_gb}GB ✓"
    fi
    
    # Check available disk space
    local disk_avail=$(df -BG "$SCRIPT_DIR" | awk 'NR==2 {print $4}' | sed 's/G//')
    if [ $disk_avail -lt 2 ]; then
        warn "Low disk space: ${disk_avail}GB available"
    else
        log "Disk space: ${disk_avail}GB available ✓"
    fi
    
    # Check CPU temperature (Pi-specific)
    if [ -f /sys/class/thermal/thermal_zone0/temp ]; then
        local temp=$(cat /sys/class/thermal/thermal_zone0/temp)
        local temp_c=$((temp / 1000))
        
        if [ $temp_c -gt 80 ]; then
            error "High CPU temperature: ${temp_c}°C. Check cooling!"
            return 1
        elif [ $temp_c -gt 70 ]; then
            warn "CPU temperature: ${temp_c}°C (getting warm)"
        else
            log "CPU temperature: ${temp_c}°C ✓"
        fi
    fi
}

# Check Docker installation
check_docker() {
    log "Checking Docker installation..."
    
    if ! command -v docker &> /dev/null; then
        error "Docker is not installed!"
        info "Install Docker with: curl -fsSL https://get.docker.com | sh"
        info "Then add your user to docker group: sudo usermod -aG docker \$USER"
        return 1
    fi
    
    # Check Docker version
    local docker_version=$(docker --version | grep -oP '\d+\.\d+\.\d+' | head -1)
    log "Docker version: $docker_version ✓"
    
    # Check if user is in docker group
    if ! groups | grep -q docker; then
        warn "User not in docker group. You may need to use sudo or add user to docker group"
    fi
    
    # Check Docker Compose
    if ! docker compose version &> /dev/null; then
        error "Docker Compose plugin not available!"
        info "Install with: sudo apt-get update && sudo apt-get install docker-compose-plugin"
        return 1
    fi
    
    local compose_version=$(docker compose version --short 2>/dev/null || echo "unknown")
    log "Docker Compose version: $compose_version ✓"
}

# Check environment configuration
check_environment() {
    log "Checking environment configuration..."
    
    if [ ! -f "$ENV_FILE" ]; then
        error ".env file not found!"
        info "Please create .env file with:"
        info "  DISCORD_BOT_TOKEN=your_bot_token"
        info "  WATCHED_FORUM_ID=your_forum_id"
        return 1
    fi
    
    # Check required variables
    source "$ENV_FILE"
    
    if [ -z "$DISCORD_BOT_TOKEN" ]; then
        error "DISCORD_BOT_TOKEN not set in .env file"
        return 1
    fi
    
    if [ -z "$WATCHED_FORUM_ID" ]; then
        error "WATCHED_FORUM_ID not set in .env file"
        return 1
    fi
    
    log "Environment configuration ✓"
}

# Create necessary directories
setup_directories() {
    log "Setting up directories..."
    
    mkdir -p "$SCRIPT_DIR/logs"
    chmod 755 "$SCRIPT_DIR/logs"
    
    log "Directories created ✓"
}

# Build Docker image
build_image() {
    log "Building Docker image for ARM architecture..."
    
    cd "$SCRIPT_DIR"
    
    # Build with explicit platform for Pi
    if ! docker compose build --no-cache; then
        error "Failed to build Docker image"
        return 1
    fi
    
    log "Docker image built successfully ✓"
}

# Deploy bot
deploy_bot() {
    log "Deploying EverQuest Forum Crafting Bot..."
    
    cd "$SCRIPT_DIR"
    
    # Stop existing container if running
    docker compose down 2>/dev/null || true
    
    # Start bot
    if ! docker compose up -d; then
        error "Failed to start bot container"
        return 1
    fi
    
    log "Bot deployed successfully ✓"
    
    # Wait a moment and check status
    sleep 5
    check_bot_status
}

# Check bot status
check_bot_status() {
    log "Checking bot status..."
    
    if docker compose ps | grep -q "Up"; then
        log "Bot container is running ✓"
        
        # Show container stats
        info "Container resource usage:"
        docker stats eq-crafting-bot --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}"
        
        return 0
    else
        error "Bot container is not running!"
        info "Check logs with: docker compose logs"
        return 1
    fi
}

# Show logs
show_logs() {
    log "Showing bot logs..."
    docker compose logs --tail=50 --follow
}

# Stop bot
stop_bot() {
    log "Stopping bot..."
    cd "$SCRIPT_DIR"
    docker compose down
    log "Bot stopped ✓"
}

# Update bot
update_bot() {
    log "Updating bot..."
    
    cd "$SCRIPT_DIR"
    
    # Pull latest code if using git
    if [ -d ".git" ]; then
        log "Pulling latest changes..."
        git pull
    fi
    
    # Rebuild and restart
    docker compose down
    docker compose build --no-cache
    docker compose up -d
    
    log "Bot updated ✓"
}

# Show system info
show_system_info() {
    echo "=== Raspberry Pi System Information ==="
    
    # Pi model
    if [ -f /proc/device-tree/model ]; then
        echo "Model: $(cat /proc/device-tree/model | tr -d '\0')"
    fi
    
    # OS info
    echo "OS: $(cat /etc/os-release | grep PRETTY_NAME | cut -d'"' -f2)"
    
    # Architecture
    echo "Architecture: $(uname -m)"
    
    # Memory
    echo "Memory: $(free -h | awk '/^Mem:/ {print $2}')"
    
    # CPU temperature
    if [ -f /sys/class/thermal/thermal_zone0/temp ]; then
        local temp=$(cat /sys/class/thermal/thermal_zone0/temp)
        local temp_c=$((temp / 1000))
        echo "CPU Temperature: ${temp_c}°C"
    fi
    
    # Docker info
    if command -v docker &> /dev/null; then
        echo "Docker: $(docker --version)"
        echo "Docker Compose: $(docker compose version --short 2>/dev/null || echo 'Not available')"
    fi
}

# Show usage
usage() {
    echo "EverQuest Forum Crafting Bot - Raspberry Pi Deployment"
    echo ""
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  deploy    - Full deployment (build and start)"
    echo "  start     - Start the bot"
    echo "  stop      - Stop the bot"
    echo "  restart   - Restart the bot"
    echo "  update    - Update and restart the bot"
    echo "  status    - Check bot status"
    echo "  logs      - Show bot logs"
    echo "  check     - Run system checks only"
    echo "  info      - Show system information"
    echo "  help      - Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 deploy         # Initial deployment"
    echo "  $0 status         # Check if bot is running"
    echo "  $0 logs           # View live logs"
}

# Main function
main() {
    case "${1:-deploy}" in
        deploy)
            log "=== EverQuest Bot - Raspberry Pi Deployment ==="
            check_raspberry_pi
            check_system_resources
            check_docker
            check_environment
            setup_directories
            build_image
            deploy_bot
            log "=== Deployment Complete! ==="
            ;;
        start)
            log "Starting bot..."
            cd "$SCRIPT_DIR"
            docker compose up -d
            check_bot_status
            ;;
        stop)
            stop_bot
            ;;
        restart)
            log "Restarting bot..."
            stop_bot
            sleep 2
            cd "$SCRIPT_DIR"
            docker compose up -d
            check_bot_status
            ;;
        update)
            update_bot
            ;;
        status)
            check_bot_status
            ;;
        logs)
            show_logs
            ;;
        check)
            log "=== System Checks ==="
            check_raspberry_pi
            check_system_resources
            check_docker
            check_environment
            ;;
        info)
            show_system_info
            ;;
        help|--help|-h)
            usage
            ;;
        *)
            error "Unknown command: $1"
            usage
            exit 1
            ;;
    esac
}

# Run main function
main "$@"