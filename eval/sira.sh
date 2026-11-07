#!/bin/bash
# 7B (kendi döngü) bitince: LangGraph 3B + 7B; görüntü v4 bitince: v5
export PYTHONIOENCODING=utf-8 LLM_BASE_URL=http://127.0.0.1:11434/v1
until grep -q '"model": "qwen2.5:7b"' eval/ajan_7b.log 2>/dev/null; do sleep 30; done
AJAN=langgraph LLM_MODEL=qwen2.5:3b .venv-lg/Scripts/python -u -m eval.calistir > eval/ajan_lg_3b.log 2>&1
AJAN=langgraph LLM_MODEL=qwen2.5:7b .venv-lg/Scripts/python -u -m eval.calistir > eval/ajan_lg_7b.log 2>&1
until grep -q "wer_temiz" eval/coklu.log; do sleep 30; done
cp eval/sonuclar/coklu_modlu.json eval/v1/coklu_modlu_v4.json
.venv/Scripts/python -u -m eval.coklu > eval/coklu_v5.log 2>&1
echo SIRA_BITTI
