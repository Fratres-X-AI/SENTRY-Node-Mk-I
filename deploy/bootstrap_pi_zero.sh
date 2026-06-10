#!/usr/bin/env bash
# SENTRY Pi Zero 2 W bootstrap — run on target as root or with sudo
set -euo pipefail

REPO="${SENTRY_REPO:-/opt/sentry-node-mk-i}"
PY="${REPO}/.venv/bin/python"

echo "[SENTRY] apt packages..."
sudo apt-get update
sudo apt-get install -y \
  python3-venv python3-pip \
  rtl-sdr librtlsdr-dev \
  portaudio19-dev libatlas-base-dev \
  git

echo "[SENTRY] blacklist DVB driver for RTL-SDR..."
grep -q 'blacklist dvb_usb_rtl28xxu' /etc/modprobe.d/rtl-sdr-blacklist.conf 2>/dev/null || \
  echo 'blacklist dvb_usb_rtl28xxu' | sudo tee /etc/modprobe.d/rtl-sdr-blacklist.conf

echo "[SENTRY] venv + install..."
cd "${REPO}/implementation"
python3 -m venv "${REPO}/.venv"
"${REPO}/.venv/bin/pip" install -U pip
"${REPO}/.venv/bin/pip" install -e ".[hardware,dev]"

echo "[SENTRY] udev + user..."
sudo groupadd -f sentry
sudo usermod -aG sentry,gpio,i2c,plugdev "${USER:-pi}" || true
sudo cp "${REPO}/deploy/99-sentry.rules" /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger

echo "[SENTRY] config..."
sudo mkdir -p /etc/sentry /var/lib/sentry
sudo cp "${REPO}/configs/sentry_node_config.json" /etc/sentry/node_config.json
sudo cp "${REPO}/configs/sentry_mission_profile.json" /etc/sentry/mission_profile.json
if [ ! -f /etc/sentry/environment ]; then
  SENTRY_KEY="$(openssl rand -hex 32)"
  printf 'SENTRY_ENV=production\nSENTRY_AUDIT_HMAC_KEY=%s\n' "${SENTRY_KEY}" | sudo tee /etc/sentry/environment >/dev/null
fi
sudo chmod 600 /etc/sentry/environment
sudo chown -R sentry:sentry /var/lib/sentry 2>/dev/null || sudo chown -R "${USER:-pi}:${USER:-pi}" /var/lib/sentry

echo "[SENTRY] systemd units..."
sudo cp "${REPO}/deploy/sentry-security.service" /etc/systemd/system/
sudo cp "${REPO}/deploy/sentry-guardian.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable sentry-security.service sentry-guardian.service

echo "[SENTRY] probe..."
"${REPO}/.venv/bin/sentry-guard" --probe --node-config /etc/sentry/node_config.json || true

echo "[SENTRY] done — run scripts/generate_manifest.py before final field deployment"
