<div align="center">

[![English](https://img.shields.io/badge/README-English-2ea44f?style=for-the-badge)](README.md)&nbsp;&nbsp;[![한국어](https://img.shields.io/badge/README-한국어-lightgrey?style=for-the-badge)](README.ko.md)

</div>

# AI Purchasing Agent — x402 pay-per-call model router

An agent that, given a user request + priority, **picks the best AI model by benchmark score**, **pays per call with x402 + ERC-3009 stablecoin micropayments**, fetches the result, and (extension) **records ERC-8004 reputation** when a result is bad.

> ✅ **Live-verified on Base Sepolia.** A real on-chain x402 payment settled end-to-end: benchmark selection → gasless ERC-3009 USDC transfer → result. Proof tx: [`0xabb329c2…b7a3`](https://sepolia.basescan.org/tx/0xabb329c2e454ea8f81bb964786a08fabffbad16afd052b0a7360c4a0cfb6b7a3) (USDC moved buyer→seller, gas paid by the facilitator).

📐 Full system diagram + sequence: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

---

## What it does

```
user request + priority ("coding, cheap")
  → [selector]  weight benchmark scores (Artificial Analysis) by priority
  → [catalog]   map the winner to a seller endpoint
  → [payer]     x402: 402 → sign ERC-3009 authorization → retry → settle
  → result
  → [judge]     score the answer
  → [reputation] if bad, ERC-8004 giveFeedback on the seller
```

**Why this shape.** As AI shifts from flat-rate to pay-per-call, the edge moves to *picking the right model and paying for it efficiently*. x402 makes per-call micropayments viable (no fixed fee), and an agent can pay autonomously (M2M). This is the buyer side of that world.

## Architecture

```
┌──────────────── Buyer Agent (Python) ────────────────┐
│ selector → catalog → payer (x402 client) → judge      │
└───────────────────────┬───────────────────────────────┘
                        │ x402 pay-per-call (USDC, Base Sepolia)
                        ▼
            ┌──────────────────────────────┐
            │  self-built x402 proxy seller │  backend = mock | heurist
            │  (FastAPI + x402 middleware)  │            | openrouter | anthropic | openai
            └──────────────────────────────┘
                        │
                        ▼ (extension, when result is bad)
            ERC-8004 Reputation Registry — giveFeedback()
```

**One seller: our x402 proxy.** As of 2026 **no third party sells pay-per-token LLM chat via x402 on testnet** — Heurist's x402 sells Mesh agent *tools* on Base **mainnet** (real USDC), and its LLM gateway is API-key only. So all LLM inference is x402-paid to our own proxy, and the real model is fulfilled by a swappable `backend` (free/mock during dev, real keys for the final run). The buyer is verified against a real third-party x402 envelope: `python scripts/probe_real_402.py`.

## Live proof

```
tx 0xabb329c2e454ea8f81bb964786a08fabffbad16afd052b0a7360c4a0cfb6b7a3   (Base Sepolia)
status   SUCCESS, block 43528892
transfer 0.001 USDC  buyer 0x29d3…5940 → seller 0x1868…9Eb5
gas      paid by facilitator 0xd407…  (buyer is gasless — ERC-3009)
```

## Run (mock — no wallet, offline)

```bash
pip install -r requirements.txt
pytest -q                                   # 17 tests

# terminal 1: x402 proxy (mock crypto, mock backend)
X402_MODE=mock PROXY_BACKEND=mock uvicorn seller_proxy.main:app --port 8402
# terminal 2: select → 402 → mock pay → result → judge
X402_MODE=mock python -m agent.main --prompt "Write binary search in Rust" --priority coding
python scripts/demo.py
```
Priority labels: `intelligence coding agentic cheap fast balanced` (combinable).
See the reputation loop: run the proxy with `PROXY_BACKEND=mock_bad` (seller returns a refusal → judge marks it bad → `giveFeedback` is written to `data/reputation_ledger.json`).

## Run (live on-chain payment — Base Sepolia testnet)

```bash
pip install "x402[evm]"
python scripts/gen_wallet.py                # writes .env with 2 throwaway testnet wallets
#  → fund the printed BUYER address at https://faucet.circle.com (Base Sepolia USDC)

set -a; . ./.env; set +a
uvicorn seller_proxy.real:app --port 8402   # terminal 1
python -m agent.main --prompt "Write binary search in Rust" --priority coding  # terminal 2
```
The printed tx hash settles on [sepolia.basescan.org](https://sepolia.basescan.org). Public facilitator (default) needs **no CDP key** — a funded wallet is enough; gas is sponsored.

### Real model answers (Phase 5)
By default the proxy runs `PROXY_BACKEND=mock` (echoes the prompt). To get a real answer from the *selected* model, leave `PROXY_BACKEND` unset so each model routes to its catalog `backend`, and set that backend's key. Cheapest path — a **free OpenRouter key ($0)** covers the open models:
```bash
# in .env: OPENROUTER_API_KEY=...   (and unset PROXY_BACKEND, or set it to openrouter_free)
# then the winning open model returns a real answer; frontier models need ANTHROPIC_API_KEY / OPENAI_API_KEY
```
`backend` per model: open models → `heurist`/`openrouter_free`, `claude-opus-4-8` → `anthropic`, `gpt-4o` → `openai`. Pick a priority that selects a model whose key you have (e.g. `--priority cheap` → an open model).

> ⚠️ In `.env`, set `PROXY_PRICE` as a **bare number** (`0.001`). A leading `$` (`$0.001`) gets shell-expanded by `set -a; . ./.env` (`$0` = script name) and corrupts the value.

## Project structure

| Path | Role |
|------|------|
| `agent/selector.py` | AA score fetch + priority→weight normalized scoring |
| `agent/catalog.py` | model → seller/backend mapping, priority presets |
| `agent/payer.py` | x402 client (mock handshake + real `x402[evm]` session) + spend guardrails |
| `agent/judge.py` | result quality verdict (heuristic; LLM-judge stub) |
| `agent/main.py` | orchestrator (request→select→pay→result→judge→feedback) |
| `seller_proxy/main.py` | mock x402-gated seller (real 402 handshake, mock crypto) |
| `seller_proxy/real.py` | real x402 seller (x402 v2 middleware + facilitator) |
| `seller_proxy/backends.py` | provider-agnostic backends |
| `reputation/feedback.py` | ERC-8004 giveFeedback (mock ledger / on-chain stub) |
| `scripts/` | `gen_wallet.py`, `demo.py`, `probe_real_402.py` |

## Phases

- ✅ **1** Benchmark selection (offline)
- ✅ **2** x402 proxy seller + payer + spend guardrails (mock crypto, real 402 handshake)
- ✅ **A** Real on-chain x402 payment — **live-verified on Base Sepolia**
- ✅ **3** Heurist reality-checked (mainnet tool seller, not testnet LLM x402) + real-402 probe
- ✅ **4** ERC-8004 reputation loop (mock ledger; on-chain stub)
- ✅ **5 (code)** Per-model backend routing (catalog `backend`) + current model ids. Real answers need one API key — see above.

## Security

- **Testnet only. Disposable wallet only.** A private key controls *all* chains — never put a MetaMask / mainnet / funded key in `.env`. `gen_wallet.py` makes throwaway keys; `.env` is gitignored and never printed.
- Spend guardrails: `MAX_USDC_PER_CALL`, `MAX_USDC_PER_SESSION` — the agent refuses to pay above caps.
- History was audited for secrets/keys before this repo went public — only disposable testnet addresses and a public Hardhat test key appear.

## Verified facts (researched + introspected, not assumed)

- x402 Python API pinned to installed **v2.14.0** (`eip155:84532` CAIP-2, not `"base-sepolia"`).
- Base Sepolia USDC `0x036CbD53842c5426634e7929541eC2318f3dCF7e`; public facilitator `https://x402.org/facilitator`.
- Heurist x402 = mainnet Mesh tools; not a testnet LLM seller (live-curled).
- ERC-8004 `giveFeedback(...)` interface + Base Sepolia Reputation Registry `0x8004B663…` (Draft — verify before on-chain use).
