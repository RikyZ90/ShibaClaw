#!/bin/bash
set -e

if [ ! -f /opt/tools/bin/gh ]; then
  echo "⏳ Installing gh CLI..."
  mkdir -p /opt/tools/bin

  # Detect architettura automaticamente
  ARCH=$(uname -m)
  case "$ARCH" in
    x86_64)  GH_ARCH="amd64" ;;
    aarch64) GH_ARCH="arm64" ;;
    armv7l)  GH_ARCH="armv6" ;;
    *)       echo "❌ GH CLI"; exit 1 ;;
  esac

  GH_VERSION="2.68.1"
  curl -fsSL "https://github.com/cli/cli/releases/download/v${GH_VERSION}/gh_${GH_VERSION}_linux_${GH_ARCH}.tar.gz" \
    | tar -xz -C /tmp

  mv /tmp/gh_${GH_VERSION}_linux_${GH_ARCH}/bin/gh /opt/tools/bin/gh
  chmod +x /opt/tools/bin/gh
  echo "✅ gh CLI installed for $ARCH!"
fi

exec "$@"