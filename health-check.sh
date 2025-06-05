#!/bin/bash

# Health check script for SkillScopeJob Docker containers
# Usage: ./health-check.sh [main|admin|all]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default ports
MAIN_PORT=8501
ADMIN_PORT=8502

check_service() {
    local service_name=$1
    local port=$2
    local url="http://localhost:${port}/_stcore/health"
    
    echo -n "Checking ${service_name} (port ${port})... "
    
    if curl -f -s "${url}" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Healthy${NC}"
        return 0
    else
        echo -e "${RED}❌ Unhealthy${NC}"
        return 1
    fi
}

check_container() {
    local container_name=$1
    echo -n "Checking container ${container_name}... "
    
    if docker ps --filter "name=${container_name}" --filter "status=running" | grep -q "${container_name}"; then
        echo -e "${GREEN}✅ Running${NC}"
        return 0
    else
        echo -e "${RED}❌ Not running${NC}"
        return 1
    fi
}

show_usage() {
    echo "Usage: $0 [main|admin|all]"
    echo "  main  - Check main application only"
    echo "  admin - Check admin dashboard only" 
    echo "  all   - Check both services (default)"
}

main() {
    local target=${1:-all}
    local exit_code=0
    
    echo "🏥 SkillScopeJob Health Check"
    echo "============================"
    
    case $target in
        "main")
            check_container "skillscopejob-main" || exit_code=1
            check_service "Main Application" $MAIN_PORT || exit_code=1
            ;;
        "admin")
            check_container "skillscopejob-admin" || exit_code=1
            check_service "Admin Dashboard" $ADMIN_PORT || exit_code=1
            ;;
        "all")
            check_container "skillscopejob-main" || exit_code=1
            check_service "Main Application" $MAIN_PORT || exit_code=1
            echo
            check_container "skillscopejob-admin" || exit_code=1
            check_service "Admin Dashboard" $ADMIN_PORT || exit_code=1
            ;;
        "help"|"-h"|"--help")
            show_usage
            exit 0
            ;;
        *)
            echo -e "${RED}Error: Unknown option '$target'${NC}"
            show_usage
            exit 1
            ;;
    esac
    
    echo
    if [ $exit_code -eq 0 ]; then
        echo -e "${GREEN}🎉 All checks passed!${NC}"
        echo "Access points:"
        if [ "$target" = "main" ] || [ "$target" = "all" ]; then
            echo "  • Main Application:  http://localhost:$MAIN_PORT"
        fi
        if [ "$target" = "admin" ] || [ "$target" = "all" ]; then
            echo "  • Admin Dashboard:   http://localhost:$ADMIN_PORT"
        fi
    else
        echo -e "${RED}❌ Some checks failed!${NC}"
        echo "Try running: docker-compose logs -f"
    fi
    
    exit $exit_code
}

# Check if curl is available
if ! command -v curl &> /dev/null; then
    echo -e "${YELLOW}Warning: curl not found. Only checking container status.${NC}"
    check_service() { return 0; }
fi

# Check if docker is available
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: docker not found. Please install Docker.${NC}"
    exit 1
fi

main "$@"
