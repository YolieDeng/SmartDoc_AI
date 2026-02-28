#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# SmartDoc AI — 前端部署脚本（从本地推送到服务器）
# 用法: ./deploy-local.sh
# ============================================================

# ---------- 配置（按需修改） ----------
SERVER="root@119.91.226.17"
NGINX_HTML_DIR="/usr/share/nginx/html"
NGINX_CONF_DIR="/etc/nginx/conf.d"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# ---------- 颜色输出 ----------
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ---------- 1. 本地构建 ----------
info "本地构建前端..."
npm run build || error "前端构建失败"

[ -d "dist" ] || error "dist 目录不存在，构建可能失败"

# ---------- 2. 推送产物到服务器 ----------
REMOTE_TMP="/tmp/smartdoc-frontend-${TIMESTAMP}"

info "推送构建产物到服务器 ${SERVER}:${REMOTE_TMP} ..."
rsync -avz dist/ "${SERVER}:${REMOTE_TMP}/"

# 推送 Nginx 配置
scp nginx.conf "${SERVER}:${REMOTE_TMP}/nginx.conf"

# ---------- 3. 服务器端操作 ----------
info "在服务器上替换静态文件..."
ssh "${SERVER}" bash -s <<REMOTE_SCRIPT
set -euo pipefail

NGINX_HTML_DIR="${NGINX_HTML_DIR}"
NGINX_CONF_DIR="${NGINX_CONF_DIR}"
REMOTE_TMP="${REMOTE_TMP}"

# 替换静态文件
echo "[INFO] 替换 Nginx 静态文件..."
rm -rf "\${NGINX_HTML_DIR}"/*
cp -a "\${REMOTE_TMP}/"* "\${NGINX_HTML_DIR}/" 2>/dev/null || true

# 更新 Nginx 配置
if [ -f "\${REMOTE_TMP}/nginx.conf" ]; then
    cp "\${REMOTE_TMP}/nginx.conf" "\${NGINX_CONF_DIR}/smartdoc-ai.conf"
    rm -f "\${REMOTE_TMP}/nginx.conf"
fi

# 检查 Nginx 配置
echo "[INFO] 检查 Nginx 配置..."
nginx -t || {
    echo "[ERROR] Nginx 配置检查失败！"
    exit 1
}

# 重载 Nginx
echo "[INFO] 重载 Nginx..."
nginx -s reload

# 清理临时文件
rm -rf "\${REMOTE_TMP}"

echo "[INFO] 前端部署完成 ✓"
REMOTE_SCRIPT

info "前端部署成功！"
