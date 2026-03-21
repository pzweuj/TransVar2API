#!/bin/bash
# HF Space 启动脚本 - 使用 transvar 官方数据库

echo "=========================================="
echo "TransVar API - HF Space Startup"
echo "=========================================="

# 检查数据库状态
echo "[Step 1] Checking database status..."
transvar config --refversion hg38
echo ""
transvar config --refversion hg19

# 测试 transvar
echo ""
echo "[Step 2] Testing transvar annotation..."
echo "Test 1: PIK3CA:p.E545K (hg38)"
transvar panno -i "PIK3CA:p.E545K" --refversion hg38 -o /dev/stdout 2>&1

echo ""
echo "Test 2: NM_006218.4:c.1633G>A (hg38)"
transvar canno -i "NM_006218.4:c.1633G>A" --refversion hg38 -o /dev/stdout 2>&1

echo ""
echo "Test 3: EGFR:p.L858R (hg38)"
transvar panno -i "EGFR:p.L858R" --refversion hg38 -o /dev/stdout 2>&1

# Start server
echo ""
echo "[Step 3] Starting server on port $PORT..."
echo "=========================================="

cd /app
exec python3 -c "import os; import uvicorn; from server import app; uvicorn.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 7860)), log_level='info')"