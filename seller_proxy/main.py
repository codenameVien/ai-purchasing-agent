"""x402-gated seller proxy (FastAPI).

Wraps any backend (mock/ollama/openrouter/anthropic/openai) behind an x402
paywall, so frontier models that don't natively speak x402 become buyable.

mock mode (default): accept any non-empty X-PAYMENT, return a deterministic fake
tx hash. Phase A swaps the verify/settle stub for a real facilitator call.

Run:  uvicorn seller_proxy.main:app --port 8402
"""
from __future__ import annotations

import base64
import hashlib
import json
import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .backends import call_backend

app = FastAPI(title="x402 seller proxy")

MODE = os.environ.get("X402_MODE", "mock")
CHAIN = os.environ.get("X402_CHAIN", "base-sepolia")
PAY_TO = os.environ.get("X402_PAY_TO", "0x000000000000000000000000000000000000dEaD")
PRICE_USDC = float(os.environ.get("PROXY_PRICE_USDC", "0.02"))


def _payment_required() -> JSONResponse:
    return JSONResponse(status_code=402, content={
        "x402Version": 1,
        "accepts": [{
            "scheme": "exact",
            "network": CHAIN,
            "maxAmountRequired": str(PRICE_USDC),
            "asset": "USDC",
            "payTo": PAY_TO,
            "resource": "/inference",
        }],
    })


def _verify_and_settle(payment_header: str, body: dict) -> str | None:
    """Return a tx hash if payment is valid, else None.

    mock: accept any non-empty header; deterministic fake tx.
    real (Phase A): POST facilitator /verify then /settle; return on-chain tx hash.
    """
    if MODE == "mock":
        if not payment_header:
            return None
        digest = hashlib.sha256((payment_header + json.dumps(body, sort_keys=True)).encode()).hexdigest()
        return "0xMOCK" + digest[:60]
    # --- Phase A: real facilitator ---
    # requests.post(f"{FACILITATOR}/verify", json=...) -> ok
    # requests.post(f"{FACILITATOR}/settle", json=...) -> {"txHash": ...}
    raise NotImplementedError("real facilitator verify/settle is wired in Phase A")


@app.post("/inference")
async def inference(request: Request):
    body = await request.json()
    payment = request.headers.get("X-PAYMENT")
    if not payment:
        return _payment_required()

    tx_hash = _verify_and_settle(payment, body)
    if not tx_hash:
        return _payment_required()

    content = call_backend(body)
    resp = JSONResponse({
        "model": body.get("model"),
        "choices": [{"message": {"role": "assistant", "content": content}}],
    })
    resp.headers["X-PAYMENT-RESPONSE"] = base64.b64encode(
        json.dumps({"txHash": tx_hash, "network": CHAIN}).encode()).decode()
    return resp


@app.get("/health")
async def health():
    return {"status": "ok", "mode": MODE, "backend": os.environ.get("PROXY_BACKEND", "mock")}
