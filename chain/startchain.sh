#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
VENV_PATH="chvenv"
NODES=("n0" "n1" "n2" "n3")
LOGS_DIR="logs"
PIDS_DIR="pids"
START_INTERVAL=10

echo -e "${BLUE}=== Blockchain Network Startup Script ===${NC}"

# Create directories for logs and PIDs
echo -e "${YELLOW}Creating directories...${NC}"
mkdir -p "$LOGS_DIR"
mkdir -p "$PIDS_DIR"

# Check if virtual environment exists
if [ ! -d "$VENV_PATH" ]; then
    echo -e "${RED}Error: Virtual environment '$VENV_PATH' not found!${NC}"
    echo -e "${YELLOW}Please create the virtual environment first:${NC}"
    echo -e "${YELLOW}python -m venv $VENV_PATH${NC}"
    exit 1
fi

# Activate virtual environment
echo -e "${YELLOW}Activating virtual environment: $VENV_PATH${NC}"
source "$VENV_PATH/bin/activate"

if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to activate virtual environment!${NC}"
    exit 1
fi

echo -e "${GREEN}Virtual environment activated successfully${NC}"

# Function to start a node
start_node() {
    local node_name=$1
    local node_dir=$2
    
    echo -e "${YELLOW}Starting node: $node_name${NC}"
    
    # Check if node directory exists
    if [ ! -d "$node_dir" ]; then
        echo -e "${RED}Error: Node directory '$node_dir' not found!${NC}"
        return 1
    fi
    
    # Check if main python file exists
    local main_file="$node_dir/main.py"
    if [ ! -f "$main_file" ]; then
        main_file="$node_dir/main${node_name:1}.py"  # e.g., main1.py for n1
    fi
    
    if [ ! -f "$main_file" ]; then
        echo -e "${RED}Error: Main Python file not found for $node_name${NC}"
        return 1
    fi
    
    # Start the node in background
    cd "$node_dir"
    nohup python "$(basename "$main_file")" > "../$LOGS_DIR/${node_name}.log" 2>&1 &
    local pid=$!
    cd - > /dev/null
    
    # Save PID
    echo $pid > "$PIDS_DIR/${node_name}.pid"
    
    # Verify the process is running
    sleep 2
    if kill -0 $pid 2>/dev/null; then
        echo -e "${GREEN}✓ Node $node_name started successfully (PID: $pid)${NC}"
        echo -e "${BLUE}  Log file: $LOGS_DIR/${node_name}.log${NC}"
        return 0
    else
        echo -e "${RED}✗ Failed to start node $node_name${NC}"
        rm -f "$PIDS_DIR/${node_name}.pid"
        return 1
    fi
}

# Function to check if node is already running
is_node_running() {
    local node_name=$1
    local pid_file="$PIDS_DIR/${node_name}.pid"
    
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if kill -0 $pid 2>/dev/null; then
            return 0  # Running
        else
            rm -f "$pid_file"  # Clean up stale PID file
            return 1  # Not running
        fi
    fi
    return 1  # Not running
}

# Start all nodes
echo -e "${BLUE}Starting blockchain nodes...${NC}"

for node in "${NODES[@]}"; do
    if is_node_running "$node"; then
        echo -e "${YELLOW}Node $node is already running${NC}"
        continue
    fi
    
    start_node "$node" "$node"
    
    if [ $? -eq 0 ] && [ "$node" != "${NODES[-1]}" ]; then
        echo -e "${BLUE}Waiting ${START_INTERVAL}s before starting next node...${NC}"
        sleep $START_INTERVAL
    fi
done

echo -e "\n${BLUE}=== Startup Summary ===${NC}"

# Display status of all nodes
for node in "${NODES[@]}"; do
    if is_node_running "$node"; then
        local pid=$(cat "$PIDS_DIR/${node}.pid")
        echo -e "${GREEN}✓ $node: RUNNING (PID: $pid)${NC}"
    else
        echo -e "${RED}✗ $node: NOT RUNNING${NC}"
    fi
done

echo -e "\n${BLUE}Blockchain network startup completed!${NC}"
echo -e "${YELLOW}Use ./stopchain.sh to stop all nodes${NC}"
echo -e "${YELLOW}Check logs in: $LOGS_DIR/${NC}"
echo -e "${YELLOW}PIDs stored in: $PIDS_DIR/${NC}"