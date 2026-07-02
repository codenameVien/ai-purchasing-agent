<div align="center">

[![English](https://img.shields.io/badge/README-English-2ea44f?style=for-the-badge)](README.md)&nbsp;&nbsp;[![한국어](https://img.shields.io/badge/README-한국어-lightgrey?style=for-the-badge)](README.ko.md)

</div>

# AI Purchasing Agent — x402 model marketplace

Say what you want in plain language; the agent **picks the best seller** from a marketplace (benchmark score + price + speed + reputation), **pays per call with x402 + ERC-3009 micropayments**, returns a **real model answer**, and records **ERC-8004 reputation** — including your 👍/👎 — so bad sellers sink next time.

> ✅ **Live-verified.** Real on-chain x402 payment on Base Sepolia ([tx `0xabb329c2…`](https://sepolia.basescan.org/tx/0xabb329c2e454ea8f81bb964786a08fabffbad16afd052b0a7360c4a0cfb6b7a3), gasless USDC transfer). Real answers via **OpenRouter** (Llama/DeepSeek/Qwen) and **Google Gemini** (2.5 Flash).

📐 System diagram + sequence: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) · 다음 할 일: [docs/ROADMAP.md](docs/ROADMAP.md) · 키/지갑: [docs/HANDOFF.md](docs/HANDOFF.md)

*(한국어: [README.ko.md](README.ko.md))*

---

## What it does

```
natural-language request  ("write a binary search in Rust", "빠르고 저렴하게")
  → [nl_priority] infer priority (coding / cheap / fast / …) from the prompt
  → [selector]    score OFFERS by benchmark × priority, then apply reputation
  → [payer]       x402: 402 → sign ERC-3009 → retry → settle
  → [backend]     real inference (OpenRouter / Gemini / …)
  → [judge]       machine delivery-check (empty/refusal/error)  ── quality is human's call
  → [reputation]  human 👍/👎 (scripts/rate.py) → feeds the NEXT selection
```

**Why this shape.** As AI shifts to pay-per-call, the edge is *picking the right model+seller and paying efficiently*. x402 enables no-fixed-fee micropayments an agent can make autonomously (M2M). This is the buyer side of that market.

## Marketplace (offers, not just models)

A **catalog entry is an offer** = one *seller* selling one *model*. The **same open model is sold by multiple sellers** who compete on **price and speed**; **reputation** (learned from feedback) shifts the winner over time.

```
same Llama 3.3, three sellers:      gamma $0.0012 / 35tps   (cheapest, slow)
                                    beta  $0.0015 / 60tps
                                    alpha $0.0020 / 90tps   (priciest, fastest)
"cheap" → gamma   "fast" → alpha   gamma turns dishonest (👎) → next time → beta
```

**One proxy fronts real models.** As of 2026 no third party sells pay-per-token LLM chat via x402 on testnet, so all inference is x402-paid to our own proxy; the real model is served by a swappable `backend` (`openrouter_free` · `gemini` · `heurist` · `anthropic` · `openai` · `mock`). Buyers can also **discover offers live**: `GET /marketplace`.

## Run (mock — no keys, offline)

```bash
cd ~/ai-purchasing-agent
pip install -r requirements.txt
pytest -q                                       # 33 tests

# terminal 1: x402 proxy (mock crypto, mock backend)
cd ~/ai-purchasing-agent
X402_MODE=mock PROXY_BACKEND=mock uvicorn seller_proxy.main:app --port 8402
# terminal 2:
cd ~/ai-purchasing-agent
X402_MODE=mock python -m agent.main --prompt "빠르고 저렴하게 요약해줘"   # NL → select → pay → judge
curl -s localhost:8402/marketplace | python3 -m json.tool                # discover offers
python scripts/rate.py gamma down                                        # human 👎 → avoided next time
python scripts/spend.py                                                  # spend summary
```

## Run (real answers — one key)

```bash
cd ~/ai-purchasing-agent && python scripts/setup_keys.py    # local, hidden input → .env
#   OpenRouter (free tier) covers open models; Gemini free tier via GEMINI_API_KEY
cd ~/ai-purchasing-agent && set -a; . ./.env; set +a
uvicorn seller_proxy.main:app --port 8402                   # PROXY_BACKEND unset → per-model routing
# terminal 2:
cd ~/ai-purchasing-agent && set -a; . ./.env; set +a
python -m agent.main --prompt "빠르게: 블록체인 한 문장 설명"   # → Gemini/OpenRouter real answer
```

## Run (live on-chain payment — Base Sepolia)

```bash
cd ~/ai-purchasing-agent
pip install "x402[evm]"
python scripts/gen_wallet.py         # throwaway wallet → .env, fund BUYER at faucet.circle.com
cd ~/ai-purchasing-agent && set -a; . ./.env; set +a
uvicorn seller_proxy.real:app --port 8402                   # X402_MODE=real
# terminal 2: python -m agent.main --prompt "..." --priority coding
```
tx settles on [sepolia.basescan.org](https://sepolia.basescan.org). Public facilitator needs **no CDP key**; gas is sponsored. Payer enforces the cap against the **actual 402 amount** and refuses over-cap before signing.

## Project structure

| Path | Role |
|------|------|
| `agent/nl_priority.py` | natural-language prompt → priority labels (rules; LLM stub) |
| `agent/selector.py` | benchmark × priority scoring over offers + reputation factor |
| `agent/catalog.py` | offers (seller × model); loaded from yaml or `/marketplace` |
| `agent/discovery.py` | fetch offers live from a marketplace endpoint |
| `agent/payer.py` | x402 client (mock + real `x402[evm]`) + spend guardrails + errors |
| `agent/judge.py` | machine delivery-check (heuristic / objective / llm modes) |
| `agent/verify.py` | objective ground-truth checks (code compiles/runs, arithmetic) |
| `agent/llm.py` | buyer-side LLM (priority inference / judging; NOT paid via x402) |
| `agent/accounting.py` | spend ledger + summary |
| `agent/main.py` | orchestrator (request→infer→select→pay→answer→judge→feedback) |
| `seller_proxy/main.py` | mock x402 seller + `GET /marketplace` discovery |
| `seller_proxy/real.py` | real x402 seller (x402 v2 middleware + facilitator) |
| `seller_proxy/backends.py` | provider-agnostic backends (openrouter/gemini/heurist/anthropic/openai/mock) |
| `reputation/feedback.py` | ERC-8004 giveFeedback + `load_reputation` (human-weighted) |
| `reputation/identity.py` | ERC-8004 Identity Registry — register a seller as an on-chain agent |
| `scripts/` | `setup_keys.py` · `gen_wallet.py` · `register_seller.py` · `rate.py` (👍/👎) · `spend.py` · `demo.py` · `probe_real_402.py` |

## Status

- ✅ Benchmark selection · NL priority · multi-seller marketplace (price/speed/reputation) · discovery endpoint
- ✅ x402 payment (mock + **real, live-verified on Base Sepolia**) · actual-amount guardrails
- ✅ Real answers (OpenRouter + Gemini, live) · delivery-check · human 👍/👎 → reputation loop · spend accounting
- ✅ LLM priority inference (`--infer llm`) · objective verification (`--judge objective`: code compiles/runs, arithmetic)
- ✅ On-chain giveFeedback wired against the **verified ERC-8004 ABI** (code + tests; live broadcast needs seller Identity-Registry registration + funded wallet)
- ✅ Real-payment hardening: pre-pay USDC balance check (abort before signing) · on-chain confirmation wait (don't trust the 200)
- ✅ Seller on-chain identity: `register_agent` + `scripts/register_seller.py` (ERC-8004 Identity Registry; code + tests — unlocks live giveFeedback once a seller is registered)
- ⬜ live registration/broadcast (needs funded testnet wallet) · CDP facilitator · dynamic per-model pricing — see `docs/ROADMAP.md`

## Security

- **Testnet + disposable wallet only.** A private key controls every chain — never put a MetaMask/mainnet/funded key in `.env`. `scripts/setup_keys.py` uses hidden local input; `.env` is gitignored and never committed (verified: no secrets in history).
- Spend guardrails: `MAX_USDC_PER_CALL` / `MAX_USDC_PER_SESSION`, checked against the real 402 amount.
- **Never paste API keys into chat or screenshots** — if exposed, revoke and reissue.

## Verified facts (researched + live, not assumed)

- x402 Python v2.14.0 (`eip155:84532` CAIP-2). Base Sepolia USDC `0x036CbD…CF7e`; public facilitator `https://x402.org/facilitator`.
- Heurist x402 = mainnet Mesh tools, not a testnet LLM seller (live-curled).
- Gemini current model `gemini-2.5-flash` (2.0 retired; verified via models API). Keys now `AQ.…` format.
- ERC-8004 `giveFeedback(...)` + Base Sepolia Reputation Registry `0x8004B663…` (Draft — verify before on-chain use).
