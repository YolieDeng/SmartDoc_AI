#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# SmartDoc AI — 一键部署（后端 + 前端）
# 用法:
#   ./deploy-all.sh               # 部署全部
#   ./deploy-all.sh --backend     # 只部署后端
#   ./deploy-all.sh --frontend    # 只部署前端
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

DEPLOY_BACKEND=true
DEPLOY_FRONTEND=true

if [ "${1:-}" = "--backend" ]; then
    DEPLOY_FRONTEND=false
elif [ "${1:-}" = "--frontend" ]; then
    DEPLOY_BACKEND=false
fi

# ---------- 后端 ----------
if [ "$DEPLOY_BACKEND" = true ]; then
    info "========== 部署后端 =========="
    cd "${SCRIPT_DIR}/backend"
    bash deploy-local.sh || error "后端部署失败"
    echo ""
fi

# ---------- 前端 ----------
if [ "$DEPLOY_FRONTEND" = true ]; then
    info "========== 部署前端 =========="
    cd "${SCRIPT_DIR}/frontend"
    bash deploy-local.sh || error "前端部署失败"
    echo ""
fi

info "全部部署完成 ✅"
