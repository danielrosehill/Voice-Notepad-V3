#!/bin/bash
# Text Injection Setup Script for Voice Notepad
# Validates and configures ydotool for Wayland text injection
#
# Tested on: Ubuntu 25.10, KDE Plasma 6, Wayland
#
# Usage: ./scripts/setup-text-injection.sh

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     Voice Notepad - Text Injection Setup                   ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo

# Detect environment
echo -e "${BLUE}[1/6] Detecting environment...${NC}"
echo "  OS: $(lsb_release -ds 2>/dev/null || cat /etc/os-release | grep PRETTY_NAME | cut -d'"' -f2)"
echo "  Desktop: ${XDG_CURRENT_DESKTOP:-Unknown}"
echo "  Session: ${XDG_SESSION_TYPE:-Unknown}"
echo "  User: $(whoami)"
echo

# Check if running on Wayland
if [ "$XDG_SESSION_TYPE" != "wayland" ]; then
    echo -e "${YELLOW}Warning: Not running on Wayland (detected: $XDG_SESSION_TYPE)${NC}"
    echo "  Text injection may work differently on X11."
    echo
fi

# Check if ydotool is installed
echo -e "${BLUE}[2/6] Checking ydotool installation...${NC}"
if command -v ydotool &> /dev/null; then
    YDOTOOL_PATH=$(which ydotool)
    echo -e "  ${GREEN}✓ ydotool found at: $YDOTOOL_PATH${NC}"
else
    echo -e "  ${RED}✗ ydotool not installed${NC}"
    echo
    echo "  To install ydotool, run:"
    echo -e "  ${YELLOW}sudo apt install ydotool${NC}"
    echo
    read -p "  Install now? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "  Installing ydotool..."
        sudo apt update && sudo apt install -y ydotool
        echo -e "  ${GREEN}✓ ydotool installed${NC}"
    else
        echo -e "  ${RED}Aborted. Please install ydotool manually.${NC}"
        exit 1
    fi
fi
echo

# Check for ydotoold daemon
echo -e "${BLUE}[3/6] Checking ydotoold daemon...${NC}"
YDOTOOLD_PIDS=$(pgrep -a ydotoold 2>/dev/null || true)
if [ -n "$YDOTOOLD_PIDS" ]; then
    echo "  Found running ydotoold processes:"
    echo "$YDOTOOLD_PIDS" | while read line; do
        echo "    $line"
    done
else
    echo -e "  ${YELLOW}! No ydotoold daemon running${NC}"
fi
echo

# Check socket
echo -e "${BLUE}[4/6] Checking ydotool socket...${NC}"
SOCKET_PATH="/tmp/.ydotool_socket"
if [ -S "$SOCKET_PATH" ]; then
    SOCKET_OWNER=$(stat -c '%U' "$SOCKET_PATH")
    SOCKET_PERMS=$(stat -c '%a' "$SOCKET_PATH")
    echo "  Socket: $SOCKET_PATH"
    echo "  Owner: $SOCKET_OWNER"
    echo "  Permissions: $SOCKET_PERMS"

    if [ "$SOCKET_OWNER" = "$(whoami)" ]; then
        echo -e "  ${GREEN}✓ Socket is owned by current user${NC}"
    else
        echo -e "  ${RED}✗ Socket is owned by '$SOCKET_OWNER', not '$(whoami)'${NC}"
        echo -e "  ${YELLOW}  This will cause text injection to fail!${NC}"
    fi
else
    echo -e "  ${YELLOW}! Socket not found at $SOCKET_PATH${NC}"
fi
echo

# Test ydotool
echo -e "${BLUE}[5/6] Testing ydotool...${NC}"
TEST_OUTPUT=$(ydotool key ctrl+a 2>&1 || true)
if echo "$TEST_OUTPUT" | grep -q "Using ydotoold backend"; then
    echo -e "  ${GREEN}✓ ydotool is using the daemon backend${NC}"
    YDOTOOL_WORKS=true
elif echo "$TEST_OUTPUT" | grep -q "backend unavailable"; then
    echo -e "  ${YELLOW}! ydotool reports: backend unavailable${NC}"
    echo "  This usually means the daemon socket is not accessible."
    YDOTOOL_WORKS=false
else
    echo "  ydotool output: $TEST_OUTPUT"
    YDOTOOL_WORKS=false
fi
echo

# Provide remediation if needed
echo -e "${BLUE}[6/6] Status and recommendations...${NC}"
echo

NEEDS_FIX=false

# Check if socket exists and is user-owned
if [ ! -S "$SOCKET_PATH" ] || [ "$(stat -c '%U' "$SOCKET_PATH" 2>/dev/null)" != "$(whoami)" ]; then
    NEEDS_FIX=true
fi

if [ "$YDOTOOL_WORKS" = false ]; then
    NEEDS_FIX=true
fi

if [ "$NEEDS_FIX" = true ]; then
    echo -e "${YELLOW}Text injection needs to be configured.${NC}"
    echo
    echo "The following commands will:"
    echo "  1. Stop any existing ydotoold daemons"
    echo "  2. Remove stale socket files"
    echo "  3. Start ydotoold as your user"
    echo
    echo -e "${YELLOW}Commands to run:${NC}"
    echo "─────────────────────────────────────────────"
    echo "sudo pkill ydotoold"
    echo "sudo rm -f /tmp/.ydotool_socket"
    echo "ydotoold &"
    echo "─────────────────────────────────────────────"
    echo
    read -p "Run these commands now? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "  Stopping existing daemons..."
        sudo pkill ydotoold 2>/dev/null || true
        sleep 0.5

        echo "  Removing stale socket..."
        sudo rm -f /tmp/.ydotool_socket
        sudo rm -f ~/.ydotool_socket
        sleep 0.5

        echo "  Starting user ydotoold..."
        ydotoold &
        sleep 1

        # Verify
        if [ -S "$SOCKET_PATH" ] && [ "$(stat -c '%U' "$SOCKET_PATH")" = "$(whoami)" ]; then
            echo -e "  ${GREEN}✓ ydotoold started successfully${NC}"
            echo -e "  ${GREEN}✓ Socket is user-owned${NC}"

            # Final test
            TEST2=$(ydotool key ctrl+a 2>&1 || true)
            if echo "$TEST2" | grep -q "Using ydotoold backend"; then
                echo -e "  ${GREEN}✓ ydotool is working correctly${NC}"
            fi
        else
            echo -e "  ${RED}✗ Something went wrong. Check the output above.${NC}"
        fi
    else
        echo "  Skipped. Run the commands manually when ready."
    fi
else
    echo -e "${GREEN}✓ Text injection is properly configured!${NC}"
    echo
    echo "  You can enable it in Voice Notepad:"
    echo "  Check the '📋 Text Injection' checkbox in the main window."
fi

echo
echo -e "${BLUE}────────────────────────────────────────────────────────────${NC}"
echo -e "${BLUE}For persistent setup (survives reboot), see:${NC}"
echo -e "${BLUE}  docs/text-injection.md${NC}"
echo -e "${BLUE}────────────────────────────────────────────────────────────${NC}"
