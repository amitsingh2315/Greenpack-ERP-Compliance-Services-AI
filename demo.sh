#!/usr/bin/env bash
# demo.sh — GreenPack EPR Service demo script
# Calls all 3 endpoints in sequence with pretty-printed JSON output.
#
# Usage:
#   chmod +x demo.sh
#   ./demo.sh
#
# Assumes the server is running at http://localhost:8000
# Start it with: uvicorn main:app --reload

BASE_URL="http://localhost:8000"

echo "========================================"
echo "  GreenPack EPR Service — API Demo"
echo "========================================"
echo ""

# ─────────────────────────────────────────────
# 1. POST /submit — Submit a declaration
# ─────────────────────────────────────────────
echo ">>> [1/3] POST /submit"
echo "Submitting plastic packaging declaration for GREENPACK-001 (2026-04)..."
echo ""

curl --silent \
     --request POST \
     --url "${BASE_URL}/submit" \
     --header "Content-Type: application/json" \
     --data '{
       "producer_id": "GREENPACK-001",
       "month": "2026-04",
       "declared_quantities_kg": {
         "rigid_plastic": 12000,
         "flexible_plastic": 8500,
         "multilayer_plastic": 3200
       }
     }' | python3 -m json.tool

echo ""
echo "----------------------------------------"
echo ""

# ─────────────────────────────────────────────
# 2. GET /summary — Reconciliation + narrative
# ─────────────────────────────────────────────
echo ">>> [2/3] GET /summary/GREENPACK-001/2026-04"
echo "Fetching reconciliation summary with LLM narrative..."
echo ""

curl --silent \
     --request GET \
     --url "${BASE_URL}/summary/GREENPACK-001/2026-04" | python3 -m json.tool

echo ""
echo "----------------------------------------"
echo ""

# ─────────────────────────────────────────────
# 3. POST /ask — RAG Q&A
# ─────────────────────────────────────────────
echo ">>> [3/3] POST /ask"
echo "Asking: 'What are the EPR registration requirements?'"
echo ""

curl --silent \
     --request POST \
     --url "${BASE_URL}/ask" \
     --header "Content-Type: application/json" \
     --data '{
       "question": "What are the EPR registration requirements?"
     }' | python3 -m json.tool

echo ""
echo "========================================"
echo "  Demo complete."
echo "========================================"
