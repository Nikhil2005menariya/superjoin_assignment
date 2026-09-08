#!/usr/bin/env bash
# Run once on a fresh Ubuntu 22.04 Lightsail instance.
# Usage: bash scripts/server-setup.sh
set -euo pipefail

echo "=== [1/4] Installing Docker ==="
apt-get update -y
apt-get install -y ca-certificates curl gnupg lsb-release git
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
  > /etc/apt/sources.list.d/docker.list
apt-get update -y
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable docker
systemctl start docker

echo "=== [2/4] Cloning repository ==="
cd /opt
git clone https://github.com/Nikhil2005menariya/superjoin_assignment.git fact-knowledge-layer
cd fact-knowledge-layer

echo "=== [3/4] Creating .env ==="
cat > .env <<'ENVEOF'
LLM_PROVIDER=bedrock
AWS_ACCESS_KEY_ID=REPLACE_ME
AWS_SECRET_ACCESS_KEY=REPLACE_ME
AWS_REGION=us-east-1
QDRANT_HOST=qdrant
QDRANT_PORT=6333
MAX_UPLOAD_SIZE_MB=200
LOG_LEVEL=INFO
ENVEOF

echo ""
echo "=== [3/4] DONE — edit /opt/fact-knowledge-layer/.env with your real AWS keys ==="
echo "    nano /opt/fact-knowledge-layer/.env"
echo ""
echo "=== [4/4] Once .env is filled, run: ==="
echo "    cd /opt/fact-knowledge-layer && docker compose up --build -d"
echo ""
echo "The first build takes 5-8 min (pip install + npm build)."
echo "fastembed model (~130MB) downloads on the first ingestion request."
