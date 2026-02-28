#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# SmartDoc AI — 后端部署脚本（从本地推送到服务器）
# 用法: ./deploy-local.sh
# ============================================================

# ---------- 配置（按需修改） ----------
SERVER="root@YOUR_SERVER_IP"
REMOTE_DIR="/opt/smartdoc-ai/backend"
SERVICE_NAME="smartdoc-ai"
BACKUP_DIR="/opt/smartdoc-ai/_backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# ---------- 颜色输出 ----------
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ---------- 1. 推送代码到服务器临时目录 ----------
REMOTE_TMP="/tmp/smartdoc-backend-${TIMESTAMP}"

info "推送后端代码到服务器 ${SERVER}:${REMOTE_TMP} ..."
rsync -avz --delete \
    --exclude '.venv/' \
    --exclude '__pycache__/' \
    --exclude '*.pyc' \
    --exclude '.env' \
    --exclude '.git/' \
    --exclude '.idea/' \
    ./ "${SERVER}:${REMOTE_TMP}/"

# ---------- 2. 服务器端操作 ----------
info "在服务器上执行部署..."
ssh "${SERVER}" bash -s <<REMOTE_SCRIPT
set -euo pipefail

REMOTE_DIR="${REMOTE_DIR}"
REMOTE_TMP="${REMOTE_TMP}"
BACKUP_DIR="${BACKUP_DIR}"
TIMESTAMP="${TIMESTAMP}"
SERVICE_NAME="${SERVICE_NAME}"
BACKUP_PATH="\${BACKUP_DIR}/backend-\${TIMESTAMP}"

# 创建必要目录
mkdir -p "\${REMOTE_DIR}" "\${BACKUP_DIR}"

# 备份旧代码
if [ -d "\${REMOTE_DIR}/app" ]; then
    echo "[INFO] 备份旧代码到 \${BACKUP_PATH} ..."
    cp -a "\${REMOTE_DIR}" "\${BACKUP_PATH}"
else
    echo "[INFO] 首次部署，跳过备份"
fi

# 保留 .env
if [ -f "\${REMOTE_DIR}/.env" ]; then
    cp "\${REMOTE_DIR}/.env" /tmp/.env.smartdoc.bak
fi

# 替换代码
echo "[INFO] 替换代码..."
rm -rf "\${REMOTE_DIR}/app" "\${REMOTE_DIR}/main.py" "\${REMOTE_DIR}/pyproject.toml" "\${REMOTE_DIR}/uv.lock"
cp -a "\${REMOTE_TMP}/"* "\${REMOTE_DIR}/"

# 还原 .env
if [ -f /tmp/.env.smartdoc.bak ]; then
    cp /tmp/.env.smartdoc.bak "\${REMOTE_DIR}/.env"
    rm -f /tmp/.env.smartdoc.bak
fi

# 安装依赖
echo "[INFO] 安装依赖 (uv sync) ..."
cd "\${REMOTE_DIR}"
uv sync --no-dev --frozen 2>&1 || uv sync --no-dev 2>&1

# 安装 systemd 服务（如果有新的 service 文件）
if [ -f "\${REMOTE_DIR}/smartdoc-ai.service" ]; then
    cp "\${REMOTE_DIR}/smartdoc-ai.service" /etc/systemd/system/\${SERVICE_NAME}.service
    systemctl daemon-reload
fi

# 重启服务
echo "[INFO] 重启 ${SERVICE_NAME} 服务..."
systemctl restart "\${SERVICE_NAME}" || {
    echo "[ERROR] 重启失败！正在回滚..."
    if [ -d "\${BACKUP_PATH}" ]; then
        rm -rf "\${REMOTE_DIR}"
        cp -a "\${BACKUP_PATH}" "\${REMOTE_DIR}"
        systemctl restart "\${SERVICE_NAME}" || echo "[ERROR] 回滚后重启仍然失败，请手动检查"
    fi
    exit 1
}

# 等待服务启动
sleep 2
if systemctl is-active --quiet "\${SERVICE_NAME}"; then
    echo "[INFO] 服务启动成功 ✓"
else
    echo "[ERROR] 服务未正常运行，请检查: journalctl -u \${SERVICE_NAME} -n 50"
    exit 1
fi

# 清理临时文件
rm -rf "\${REMOTE_TMP}"

# 清理旧备份（保留最近 5 个）
cd "\${BACKUP_DIR}"
ls -dt backend-* 2>/dev/null | tail -n +6 | xargs rm -rf 2>/dev/null || true

echo "[INFO] 后端部署完成 ✓"
REMOTE_SCRIPT

info "后端部署成功！"
