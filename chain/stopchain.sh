#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
NODES=("n0" "n1" "n2" "n3")
LOGS_DIR="logs"
PIDS_DIR="pids"
FORCE_KILL_TIMEOUT=5

echo -e "${BLUE}=== Blockchain Network Shutdown Script ===${NC}"

# Function to stop a node
stop_node() {
    local node_name=$1
    local pid_file="$PIDS_DIR/${node_name}.pid"
    
    if [ ! -f "$pid_file" ]; then
        echo -e "${YELLOW}No PID file found for $node_name (already stopped?)${NC}"
        return 0
    fi
    
    local pid=$(cat "$pid_file")
    
    # Check if process is still running
    if ! kill -0 $pid 2>/dev/null; then
        echo -e "${YELLOW}Node $node_name (PID: $pid) is not running${NC}"
        rm -f "$pid_file"
        return 0
    fi
    
    echo -e "${YELLOW}Stopping node: $node_name (PID: $pid)${NC}"
    
    # Try graceful shutdown first
    kill -TERM $pid 2>/dev/null
    
    # Wait for graceful shutdown
    local count=0
    while kill -0 $pid 2>/dev/null && [ $count -lt $FORCE_KILL_TIMEOUT ]; do
        sleep 1
        ((count++))
        echo -e "${BLUE}  Waiting for graceful shutdown... ($count/${FORCE_KILL_TIMEOUT}s)${NC}"
    done
    
    # Force kill if still running
    if kill -0 $pid 2>/dev/null; then
        echo -e "${YELLOW}  Force killing node $node_name${NC}"
        kill -KILL $pid 2>/dev/null
        sleep 1
    fi
    
    # Verify the process is stopped
    if kill -0 $pid 2>/dev/null; then
        echo -e "${RED}✗ Failed to stop node $node_name${NC}"
        return 1
    else
        echo -e "${GREEN}✓ Node $node_name stopped successfully${NC}"
        rm -f "$pid_file"
        return 0
    fi
}

# Function to clean up orphaned processes
cleanup_orphaned_processes() {
    echo -e "${YELLOW}Checking for orphaned blockchain processes...${NC}"
    
    # Look for Python processes that might be our nodes
    local orphaned_pids=$(pgrep -f "python.*main.*\.py" 2>/dev/null || true)
    
    if [ -n "$orphaned_pids" ]; then
        echo -e "${YELLOW}Found potential orphaned processes:${NC}"
        for pid in $orphaned_pids; do
            local cmd=$(ps -p $pid -o cmd= 2>/dev/null || echo "Unknown")
            echo -e "${YELLOW}  PID $pid: $cmd${NC}"
        done
        
        read -p "Do you want to kill these processes? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            for pid in $orphaned_pids; do
                kill -TERM $pid 2>/dev/null || true
                sleep 1
                if kill -0 $pid 2>/dev/null; then
                    kill -KILL $pid 2>/dev/null || true
                fi
                echo -e "${GREEN}✓ Killed process $pid${NC}"
            done
        fi
    else
        echo -e "${GREEN}No orphaned processes found${NC}"
    fi
}

# Stop all nodes
echo -e "${BLUE}Stopping blockchain nodes...${NC}"

for node in "${NODES[@]}"; do
    stop_node "$node"
done

# Clean up directories
echo -e "\n${YELLOW}Cleaning up...${NC}"

# Remove PID files (should be empty by now, but just in case)
if [ -d "$PIDS_DIR" ]; then
    rm -f "$PIDS_DIR"/*.pid
    rmdir "$PIDS_DIR" 2>/dev/null || true
    echo -e "${GREEN}✓ Cleaned up PID files${NC}"
fi

# Handle log files
if [ -d "$LOGS_DIR" ]; then
    log_count=$(ls -1 "$LOGS_DIR"/*.log 2>/dev/null | wc -l)
    if [ $log_count -gt 0 ]; then
        echo -e "${YELLOW}Found $log_count log files in $LOGS_DIR${NC}"
        read -p "Do you want to delete log files? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -f "$LOGS_DIR"/*.log
            rmdir "$LOGS_DIR" 2>/dev/null || true
            echo -e "${GREEN}✓ Deleted log files${NC}"
        else
            echo -e "${BLUE}Log files preserved in $LOGS_DIR${NC}"
        fi
    else
        rmdir "$LOGS_DIR" 2>/dev/null || true
    fi
fi

# Check for orphaned processes
cleanup_orphaned_processes

echo -e "\n${BLUE}=== Shutdown Summary ===${NC}"

# Verify all nodes are stopped
all_stopped=true
for node in "${NODES[@]}"; do
    pid_file="$PIDS_DIR/${node}.pid"
    if [ -f "$pid_file" ]; then
        pid=$(cat "$pid_file")
        if kill -0 $pid 2>/dev/null; then
            echo -e "${RED}✗ $node: STILL RUNNING (PID: $pid)${NC}"
            all_stopped=false
        else
            echo -e "${GREEN}✓ $node: STOPPED${NC}"
        fi
    else
        echo -e "${GREEN}✓ $node: STOPPED${NC}"
    fi
done

if [ "$all_stopped" = true ]; then
    echo -e "\n${GREEN}All blockchain nodes stopped successfully!${NC}"
else
    echo -e "\n${YELLOW}Some nodes may still be running. Check manually if needed.${NC}"
fi

# Deactivate virtual environment if it was activated by this script
if [ -n "$VIRTUAL_ENV" ]; then
    echo -e "${YELLOW}Note: Virtual environment is still active. Use 'deactivate' to exit.${NC}"
fi