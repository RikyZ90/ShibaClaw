#!/bin/bash

# ShibaClaw Automated Installer for Linux/macOS
# This script installs Python, creates a venv, and installs shibaclaw via PyPI.

set -e

echo ">> Starting ShibaClaw installation..."

# 1. Check/Install Python and Venv
if ! command -v python3 &> /dev/null; then
    echo "[!] Python 3 not found. Attempting to install..."
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        if command -v apt-get &> /dev/null; then
            echo ">> Detected Debian/Ubuntu. Installing python3 and venv via apt..."
            sudo apt-get update && sudo apt-get install -y python3 python3-venv
        else
            echo "[!] Unsupported Linux distro for auto-install. Please install Python 3.12+ and python3-venv manually."
            exit 1
        fi
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        if command -v brew &> /dev/null; then
            echo ">> Detected macOS. Installing python via Homebrew..."
            brew install python
        else
            echo "[!] Homebrew not found. Please install Python 3.12+ manually or install Homebrew first."
            exit 1
        fi
    else
        echo "[!] Unsupported OS. Please install Python 3.12+ manually."
        exit 1
    fi
fi

# Ensure venv module is present (critical for Ubuntu)
if ! python3 -m venv --help &> /dev/null; then
    echo ">> Python found, but venv module is missing. Attempting to install..."
    if command -v apt-get &> /dev/null; then
        sudo apt-get update && sudo apt-get install -y python3-venv
    else
        echo "[!] Could not install python3-venv automatically. Please install it manually."
        exit 1
    fi
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PY_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)
if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 12 ]; }; then
    echo "[!] Python $PYTHON_VERSION is too old. ShibaClaw requires Python 3.12+."
    echo "   Please install Python 3.12+ manually (e.g. from https://python.org or deadsnakes PPA)."
    exit 1
fi
echo "[OK] Found Python $PYTHON_VERSION"

# 2. Installation Method (Prefer pipx, fallback to venv+pip)
if command -v pipx &> /dev/null; then
    echo ">> pipx detected. Using pipx for a cleaner installation..."
    pipx install shibaclaw
    SHIBA_EXEC="shibaclaw"
    if ! command -v shibaclaw &> /dev/null; then
        if [ -f "$HOME/.local/bin/shibaclaw" ]; then
            SHIBA_EXEC="$HOME/.local/bin/shibaclaw"
        fi
    fi
else
    echo ">> pipx not found. Falling back to manual venv + pip..."
    INSTALL_DIR="$HOME/.shibaclaw"
    VENV_DIR="$INSTALL_DIR/venv"
    mkdir -p "$INSTALL_DIR"

    echo ">> Creating virtual environment in $VENV_DIR..."
    python3 -m venv "$VENV_DIR"

    echo ">> Installing shibaclaw from PyPI..."
    "$VENV_DIR/bin/pip" install --upgrade pip
    "$VENV_DIR/bin/pip" install shibaclaw

    BIN_PATH="/usr/local/bin/shibaclaw"
    if [ -w "/usr/local/bin" ]; then
        echo ">> Creating symbolic link in /usr/local/bin..."
        ln -sf "$VENV_DIR/bin/shibaclaw" "$BIN_PATH"
        SHIBA_EXEC="$BIN_PATH"
    else
        echo "[!] Could not write to /usr/local/bin. You can run shibaclaw using: $VENV_DIR/bin/shibaclaw"
        SHIBA_EXEC="$VENV_DIR/bin/shibaclaw"
    fi
fi

echo ">> Starting ShibaClaw..."

# 5. Run WebUI and Gateway
$SHIBA_EXEC web --with-gateway
