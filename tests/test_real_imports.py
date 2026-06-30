"""Phase A guard: real x402 paths import + construct offline (no network, no funds).

Proves the x402 v2.14.0 API names/signatures used in real mode are valid, without
making an on-chain payment. The live paid call is exercised via the README runbook.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import requests

# Well-known throwaway test key (NOT a real wallet). Phase A uses a funded testnet key.
_TEST_KEY = "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d"


def test_buyer_session_constructs_offline():
    os.environ["WALLET_PRIVATE_KEY"] = _TEST_KEY
    from agent.payer import build_paying_session
    session = build_paying_session(network="eip155:84532")
    assert isinstance(session, requests.Session)


def test_seller_real_api_symbols_valid():
    # Same imports seller_proxy/real.py uses; constructing the payment option is
    # offline, which validates the v2 API names without building the app (network).
    from x402.http import PaymentOption
    from x402.http.facilitator_client_base import CreateHeadersAuthProvider  # noqa: F401
    from x402.http.middleware.fastapi import PaymentMiddlewareASGI  # noqa: F401
    from x402.http.types import RouteConfig
    from x402.server import x402ResourceServer  # noqa: F401

    opt = PaymentOption(scheme="exact",
                        pay_to="0x000000000000000000000000000000000000dEaD",
                        price="$0.02", network="eip155:84532")
    route = RouteConfig(accepts=opt)
    assert route.accepts is opt
