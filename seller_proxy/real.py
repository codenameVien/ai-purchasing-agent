"""Real x402-gated seller using the x402 v2 library + a facilitator.

All x402 symbols below were verified against installed x402 v2.14.0
(pip install "x402[evm]").

Default facilitator = public testnet (https://x402.org/facilitator, no auth), so a
funded Base Sepolia wallet alone is enough for a real on-chain payment. Set CDP
creds (CDP_API_KEY_ID / CDP_API_KEY_SECRET) to use the Coinbase CDP hosted
facilitator instead.

Run:  X402_MODE=real X402_PAY_TO=0x... uvicorn seller_proxy.real:app --port 8402

Importing this module builds the app, which mounts the payment middleware (the
facilitator may be queried at startup) — so it requires X402_PAY_TO to be set.
"""
from __future__ import annotations

import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from x402.http import FacilitatorConfig, HTTPFacilitatorClient, PaymentOption
from x402.http.facilitator_client_base import CreateHeadersAuthProvider
from x402.http.middleware.fastapi import PaymentMiddlewareASGI
from x402.http.types import RouteConfig
from x402.mechanisms.evm.exact import register_exact_evm_server
from x402.server import x402ResourceServer

from .backends import call_backend


def _cdp_create_headers():
    """Return a CDP create_headers callable if CDP creds are set, else None.

    The JWT-minting helper ships in the `cdp-sdk` package; wire it here once you
    have CDP creds. The public facilitator (default) needs none, so this stays
    None for a no-CDP testnet run.
    """
    if not (os.environ.get("CDP_API_KEY_ID") and os.environ.get("CDP_API_KEY_SECRET")):
        return None
    # from cdp.x402 import create_facilitator_headers   # verify exact name in cdp-sdk
    raise NotImplementedError(
        "CDP facilitator auth: install cdp-sdk and return its create_headers here. "
        "The default public facilitator requires no CDP creds.")


def _facilitator() -> HTTPFacilitatorClient:
    url = os.environ.get("X402_FACILITATOR_URL", "https://x402.org/facilitator")
    create_headers = _cdp_create_headers()
    cfg = FacilitatorConfig(
        url=url,
        auth_provider=CreateHeadersAuthProvider(create_headers) if create_headers else None,
    )
    return HTTPFacilitatorClient(cfg)


def build_app() -> FastAPI:
    app = FastAPI(title="x402 seller proxy (real)")

    @app.post("/inference")
    async def inference(request: Request):
        # Reached only AFTER the payment middleware has verified payment.
        body = await request.json()
        content = call_backend(body)
        return JSONResponse({
            "model": body.get("model"),
            "choices": [{"message": {"role": "assistant", "content": content}}],
        })

    pay_to = os.environ["X402_PAY_TO"]                       # seller's receiving address
    network = os.environ.get("X402_NETWORK", "eip155:84532")  # Base Sepolia (CAIP-2)
    price = os.environ.get("PROXY_PRICE", "$0.02")            # Money string -> network USDC
    server = x402ResourceServer(facilitator_clients=_facilitator())
    register_exact_evm_server(server, networks=network)   # enable "exact" EVM scheme for the seller
    routes = {
        "/inference": RouteConfig(
            accepts=PaymentOption(scheme="exact", pay_to=pay_to, price=price, network=network),
        ),
    }
    app.add_middleware(PaymentMiddlewareASGI, routes=routes, server=server)
    return app


app = build_app()
