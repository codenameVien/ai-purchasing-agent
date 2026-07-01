# AI Purchasing Agent — x402 pay-per-call model router

An agent that, given a user request + priority, **picks the best AI model by benchmark score**, **pays per call with x402 + ERC-3009 stablecoin micropayments**, fetches the result, and (extension) **records ERC-8004 reputation** when a result is bad.

> ✅ **Live-verified on Base Sepolia.** A real on-chain x402 payment settled end-to-end: benchmark selection → gasless ERC-3009 USDC transfer → result. Proof tx: [`0xabb329c2…b7a3`](https://sepolia.basescan.org/tx/0xabb329c2e454ea8f81bb964786a08fabffbad16afd052b0a7360c4a0cfb6b7a3) (USDC moved buyer→seller, gas paid by the facilitator).

*(한국어 설명은 아래 [## 한국어](#한국어) 참고.)*

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
- ✅ **5 (code)** Per-model backend routing (catalog `backend`) + current model ids. Real answers need one API key — see below.

## Security

- **Testnet only. Disposable wallet only.** A private key controls *all* chains — never put a MetaMask / mainnet / funded key in `.env`. `gen_wallet.py` makes throwaway keys; `.env` is gitignored and never printed.
- Spend guardrails: `MAX_USDC_PER_CALL`, `MAX_USDC_PER_SESSION` — the agent refuses to pay above caps.
- Wallet/payment/signing code is sensitive → this repo stays **private** unless audited for public release.

## Verified facts (researched + introspected, not assumed)

- x402 Python API pinned to installed **v2.14.0** (`eip155:84532` CAIP-2, not `"base-sepolia"`).
- Base Sepolia USDC `0x036CbD53842c5426634e7929541eC2318f3dCF7e`; public facilitator `https://x402.org/facilitator`.
- Heurist x402 = mainnet Mesh tools; not a testnet LLM seller (live-curled).
- ERC-8004 `giveFeedback(...)` interface + Base Sepolia Reputation Registry `0x8004B663…` (Draft — verify before on-chain use).

---

# 한국어

사용자 요청 + 우선순위를 받아 **벤치마크 점수로 가장 맞는 AI 모델을 고르고**, **x402 + ERC-3009 스테이블코인 마이크로페이먼트로 호출당 결제**해 결과를 받아오며, (확장) 결과가 나쁘면 **ERC-8004 평판에 기록**하는 구매 에이전트.

> ✅ **Base Sepolia에서 라이브 검증 완료.** 실제 온체인 x402 결제가 e2e로 정산됨: 벤치마크 선택 → 가스리스 ERC-3009 USDC 이동 → 결과. 증거 tx: [`0xabb329c2…b7a3`](https://sepolia.basescan.org/tx/0xabb329c2e454ea8f81bb964786a08fabffbad16afd052b0a7360c4a0cfb6b7a3).

## 무엇을 하나

```
사용자 요청 + 우선순위 ("coding, 저렴하게")
  → [selector]  Artificial Analysis 점수를 우선순위 가중치로 스코어링
  → [catalog]   선택된 모델 → 셀러 엔드포인트 매핑
  → [payer]     x402: 402 → ERC-3009 서명 → 재요청 → 정산
  → 결과
  → [judge]     답변 품질 평가
  → [reputation] 나쁘면 ERC-8004 giveFeedback
```

**왜 이 구조인가.** AI가 정액제→종량제로 가면 경쟁력은 *맞는 모델을 골라 효율적으로 사 쓰는 능력*으로 이동한다. x402가 고정수수료 없는 호출당 마이크로페이먼트를 가능케 하고, 에이전트가 자율 결제(M2M)할 수 있다. 이 프로젝트는 그 세계의 구매자 측이다.

## 구조

모든 LLM 추론은 x402로 **우리 프록시**에 결제하고, 실제 모델은 교체식 `backend`(개발=무료/mock, 최종=실키)가 수행한다. **이유:** 2026년 현재 테스트넷에 pay-per-token LLM을 x402로 파는 제3자 셀러가 없다 — Heurist x402는 Base **메인넷**에서 Mesh 에이전트 *툴*(실 USDC)을 팔고, LLM 게이트웨이는 API키 인증이라 x402가 아니다. 단 버이어가 진짜 제3자 x402 봉투를 파싱함은 검증됨(`scripts/probe_real_402.py`).

## 라이브 증거

```
tx 0xabb329c2…b7a3 (Base Sepolia) — SUCCESS
USDC 0.001 이동: 구매자 0x29d3…5940 → 판매자 0x1868…9Eb5
가스: facilitator 0xd407…가 대납 (구매자 가스리스, ERC-3009)
```

## 실행 (mock — 지갑 불필요)

```bash
pip install -r requirements.txt
pytest -q
X402_MODE=mock PROXY_BACKEND=mock uvicorn seller_proxy.main:app --port 8402   # 터미널1
X402_MODE=mock python -m agent.main --prompt "Write binary search in Rust" --priority coding  # 터미널2
```
우선순위 라벨: `intelligence coding agentic cheap fast balanced` (복수 지정). 평판 루프는 프록시를 `PROXY_BACKEND=mock_bad`로 띄우면 확인(거부 응답 → bad 판정 → `data/reputation_ledger.json`에 기록).

## 실행 (라이브 온체인 결제 — 테스트넷)

```bash
pip install "x402[evm]"
python scripts/gen_wallet.py        # 일회용 테스트넷 지갑 2개 + .env 생성
#  → 출력된 BUYER 주소를 faucet.circle.com(Base Sepolia)에서 USDC 충전
set -a; . ./.env; set +a
uvicorn seller_proxy.real:app --port 8402   # 터미널1
python -m agent.main --prompt "..." --priority coding  # 터미널2
```
출력 tx hash를 sepolia.basescan.org에서 확인. 공개 facilitator 기본이라 **CDP 키 불필요** — 펀딩 지갑만 있으면 됨(가스 대납).

> ⚠️ `.env`의 `PROXY_PRICE`는 **bare 숫자**(`0.001`). `$0.001`로 쓰면 `set -a; . ./.env`가 `$0`(스크립트명)을 확장해 깨진다.

## 단계

- ✅ **1** 벤치마크 선택 (오프라인)
- ✅ **2** x402 프록시 셀러 + payer + 지출 가드레일 (암호화만 mock, 402 핸드셰이크는 실제)
- ✅ **A** 실 온체인 x402 결제 — **Base Sepolia 라이브 검증**
- ✅ **3** Heurist 현실 검증(메인넷 툴 셀러, 테스트넷 LLM x402 아님) + real-402 프로브
- ✅ **4** ERC-8004 평판 루프 (mock 원장; 온체인 스텁)
- ✅ **5 (코드)** 모델별 백엔드 라우팅(catalog `backend`) + 현재 모델 id. 진짜 답변은 키 1개 필요(무료 OpenRouter 키면 $0). `PROXY_BACKEND` 안 정하면 모델마다 자기 backend로 라우팅.

## 보안

- **테스트넷 전용. 일회용 지갑만.** 개인키는 *모든* 체인을 통제 — 메타마스크/메인넷/자산 든 키를 `.env`에 절대 금지. `gen_wallet.py`가 일회용 키 생성, `.env`는 gitignore + 출력 안 함.
- 지출 가드레일: `MAX_USDC_PER_CALL`, `MAX_USDC_PER_SESSION` 초과 시 결제 거부.
- 지갑·결제·서명 코드는 민감 → 공개 검토 전까지 repo **private** 유지.
