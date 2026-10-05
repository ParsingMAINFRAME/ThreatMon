#!/usr/bin/env bash
# One-time setup for an Ubuntu server (Oracle Cloud Always Free, or any Ubuntu 22.04/24.04 VM).
# Installs Docker, opens ports 80/443 in the host firewall, adds swap on small machines,
# writes deploy/.env and starts the API, news poller and console behind HTTPS.
# Safe to re-run. Usage, from the repository root on the server:
#   ./deploy/setup-server.sh [site-address]
set -euo pipefail

cd "$(dirname "$0")/.."

if ! command -v docker >/dev/null 2>&1; then
  echo "Installing Docker"
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker "$USER"
fi

# Oracle's Ubuntu images ship iptables rules that reject everything except SSH, even when the
# cloud security list allows the port. Insert accept rules ahead of that reject rule.
if command -v iptables >/dev/null 2>&1; then
  for port in 80 443; do
    sudo iptables -C INPUT -p tcp --dport "$port" -j ACCEPT 2>/dev/null \
      || sudo iptables -I INPUT 1 -p tcp --dport "$port" -j ACCEPT
  done
  sudo iptables -C INPUT -p udp --dport 443 -j ACCEPT 2>/dev/null \
    || sudo iptables -I INPUT 1 -p udp --dport 443 -j ACCEPT
  if [ -d /etc/iptables ]; then
    sudo sh -c 'iptables-save > /etc/iptables/rules.v4'
  fi
fi

# Building the console needs about 2 GB of memory; add swap on machines with less than 3 GB.
memory_kb=$(awk '/MemTotal/ {print $2}' /proc/meminfo)
if [ "$memory_kb" -lt 3000000 ] && ! swapon --show | grep -q /swapfile; then
  echo "Adding 2 GB swap"
  sudo fallocate -l 2G /swapfile
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile
  grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
fi

if [ ! -f deploy/.env ]; then
  cp deploy/server.env.example deploy/.env
fi
site="${1:-}"
if [ -z "$site" ]; then
  site=$(grep -E '^SITE_ADDRESS=' deploy/.env | cut -d= -f2-)
fi
if [ -z "$site" ]; then
  public_ip=$(curl -fsS https://checkip.amazonaws.com | tr -d '[:space:]')
  site="${public_ip//./-}.sslip.io"
fi
sed -i "s|^SITE_ADDRESS=.*|SITE_ADDRESS=$site|" deploy/.env

compose=(docker compose -f docker-compose.yml -f deploy/docker-compose.server.yml --env-file deploy/.env)
if ! docker info >/dev/null 2>&1; then
  compose=(sudo "${compose[@]}")
fi
"${compose[@]}" up -d --build --wait

echo
echo "ThreatMon is running at https://$site"
echo "The news poller refreshes every 15 minutes. Logs: ${compose[*]} logs -f poller"
