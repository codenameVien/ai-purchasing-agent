<div align="center">

[![English](https://img.shields.io/badge/README-English-lightgrey?style=for-the-badge)](README.md)&nbsp;&nbsp;[![한국어](https://img.shields.io/badge/README-한국어-2ea44f?style=for-the-badge)](README.ko.md)

</div>

# AI Purchasing Agent — x402 호출당 결제 모델 라우터

사용자 요청 + 우선순위를 받아 **벤치마크 점수로 가장 맞는 AI 모델을 고르고**, **x402 + ERC-3009 스테이블코인 마이크로페이먼트로 호출당 결제**해 결과를 받아오며, (확장) 결과가 나쁘면 **ERC-8004 평판에 기록**하는 구매 에이전트.

> ✅ **Base Sepolia에서 라이브 검증 완료.** 실제 온체인 x402 결제가 e2e로 정산됨: 벤치마크 선택 → 가스리스 ERC-3009 USDC 이동 → 결과. 증거 tx: [`0xabb329c2…b7a3`](https://sepolia.basescan.org/tx/0xabb329c2e454ea8f81bb964786a08fabffbad16afd052b0a7360c4a0cfb6b7a3) (구매자→판매자 USDC 이동, 가스는 facilitator 대납).

📐 전체 시스템 구성도 + 시퀀스: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

---

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

```
┌──────────────── 구매 에이전트 (Python) ───────────────┐
│ selector → catalog → payer (x402 클라이언트) → judge   │
└───────────────────────┬────────────────────────────────┘
                        │ x402 호출당 결제 (USDC, Base Sepolia)
                        ▼
            ┌──────────────────────────────┐
            │  자체 x402 프록시 셀러          │  backend = mock | heurist
            │  (FastAPI + x402 미들웨어)     │            | openrouter | anthropic | openai
            └──────────────────────────────┘
                        │
                        ▼ (확장, 결과가 나쁠 때)
            ERC-8004 Reputation Registry — giveFeedback()
```

모든 LLM 추론은 x402로 **우리 프록시**에 결제하고, 실제 모델은 교체식 `backend`(개발=무료/mock, 최종=실키)가 수행한다. **이유:** 2026년 현재 테스트넷에 pay-per-token LLM을 x402로 파는 제3자 셀러가 없다 — Heurist x402는 Base **메인넷**에서 Mesh 에이전트 *툴*(실 USDC)을 팔고, LLM 게이트웨이는 API키 인증이라 x402가 아니다. 단 버이어가 진짜 제3자 x402 봉투를 파싱함은 검증됨(`scripts/probe_real_402.py`).

## 라이브 증거

```
tx 0xabb329c2…b7a3 (Base Sepolia) — SUCCESS
USDC 0.001 이동: 구매자 0x29d3…5940 → 판매자 0x1868…9Eb5
가스: facilitator 0xd407…가 대납 (구매자 가스리스, ERC-3009)
```

## 실행 (mock — 지갑 불필요, 오프라인)

```bash
pip install -r requirements.txt
pytest -q                                   # 17 테스트

# 터미널1: x402 프록시 (암호화 mock, 백엔드 mock)
X402_MODE=mock PROXY_BACKEND=mock uvicorn seller_proxy.main:app --port 8402
# 터미널2: 선택 → 402 → mock 결제 → 결과 → 평가
X402_MODE=mock python -m agent.main --prompt "Write binary search in Rust" --priority coding
python scripts/demo.py
```
우선순위 라벨: `intelligence coding agentic cheap fast balanced` (복수 지정). 평판 루프는 프록시를 `PROXY_BACKEND=mock_bad`로 띄우면 확인(거부 응답 → bad 판정 → `data/reputation_ledger.json`에 기록).

## 실행 (라이브 온체인 결제 — Base Sepolia 테스트넷)

```bash
pip install "x402[evm]"
python scripts/gen_wallet.py        # 일회용 테스트넷 지갑 2개 + .env 생성
#  → 출력된 BUYER 주소를 faucet.circle.com(Base Sepolia)에서 USDC 충전
set -a; . ./.env; set +a
uvicorn seller_proxy.real:app --port 8402   # 터미널1
python -m agent.main --prompt "Write binary search in Rust" --priority coding  # 터미널2
```
출력 tx hash를 [sepolia.basescan.org](https://sepolia.basescan.org)에서 확인. 공개 facilitator 기본이라 **CDP 키 불필요** — 펀딩 지갑만 있으면 됨(가스 대납).

### 진짜 모델 답변 (Phase 5)
기본은 `PROXY_BACKEND=mock`(프롬프트 echo). *선택된* 모델의 진짜 답변을 보려면 `PROXY_BACKEND`를 비워 모델마다 카탈로그 `backend`로 라우팅되게 하고, 그 backend 키를 설정. 가장 싼 길 — **무료 OpenRouter 키($0)**로 오픈모델 커버:
```bash
# .env: OPENROUTER_API_KEY=...  (PROXY_BACKEND 비우거나 openrouter_free로)
# winner가 오픈모델이면 진짜 답변; 프론티어는 ANTHROPIC_API_KEY / OPENAI_API_KEY 필요
```
모델별 `backend`: 오픈모델 → `heurist`/`openrouter_free`, `claude-opus-4-8` → `anthropic`, `gpt-4o` → `openai`. 가진 키에 맞는 모델이 뽑히도록 우선순위 선택(예: `--priority cheap` → 오픈모델).

> ⚠️ `.env`의 `PROXY_PRICE`는 **bare 숫자**(`0.001`). `$0.001`로 쓰면 `set -a; . ./.env`가 `$0`(스크립트명)을 확장해 깨진다.

## 프로젝트 구조

| 경로 | 역할 |
|------|------|
| `agent/selector.py` | AA 점수 fetch + 우선순위→가중치 정규화 스코어링 |
| `agent/catalog.py` | 모델 → 셀러/backend 매핑, 우선순위 프리셋 |
| `agent/payer.py` | x402 클라이언트 (mock 핸드셰이크 + real `x402[evm]` 세션) + 지출 가드레일 |
| `agent/judge.py` | 결과 품질 판정 (휴리스틱; LLM-judge 스텁) |
| `agent/main.py` | 오케스트레이터 (요청→선택→결제→결과→평가→피드백) |
| `seller_proxy/main.py` | mock x402 셀러 (402 핸드셰이크 진짜, 암호화 mock) |
| `seller_proxy/real.py` | real x402 셀러 (x402 v2 미들웨어 + facilitator) |
| `seller_proxy/backends.py` | provider-agnostic 백엔드 |
| `reputation/feedback.py` | ERC-8004 giveFeedback (mock 원장 / 온체인 스텁) |
| `scripts/` | `gen_wallet.py`, `demo.py`, `probe_real_402.py` |

## 단계

- ✅ **1** 벤치마크 선택 (오프라인)
- ✅ **2** x402 프록시 셀러 + payer + 지출 가드레일 (암호화만 mock, 402 핸드셰이크는 실제)
- ✅ **A** 실 온체인 x402 결제 — **Base Sepolia 라이브 검증**
- ✅ **3** Heurist 현실 검증(메인넷 툴 셀러, 테스트넷 LLM x402 아님) + real-402 프로브
- ✅ **4** ERC-8004 평판 루프 (mock 원장; 온체인 스텁)
- ✅ **5 (코드)** 모델별 백엔드 라우팅(catalog `backend`) + 현재 모델 id. 진짜 답변은 키 1개 필요(무료 OpenRouter 키면 $0).

## 보안

- **테스트넷 전용. 일회용 지갑만.** 개인키는 *모든* 체인을 통제 — 메타마스크/메인넷/자산 든 키를 `.env`에 절대 금지. `gen_wallet.py`가 일회용 키 생성, `.env`는 gitignore + 출력 안 함.
- 지출 가드레일: `MAX_USDC_PER_CALL`, `MAX_USDC_PER_SESSION` 초과 시 결제 거부.
- 공개 전 히스토리 시크릿/키 감사 완료 — 일회용 테스트넷 주소와 공개 Hardhat 테스트키만 존재.

## 검증된 사실 (리서치 + introspect, 추측 아님)

- x402 Python API = 설치본 **v2.14.0** (`eip155:84532` CAIP-2, `"base-sepolia"` 아님).
- Base Sepolia USDC `0x036CbD53842c5426634e7929541eC2318f3dCF7e`; 공개 facilitator `https://x402.org/facilitator`.
- Heurist x402 = 메인넷 Mesh 툴; 테스트넷 LLM 셀러 아님 (라이브 curl 확인).
- ERC-8004 `giveFeedback(...)` 인터페이스 + Base Sepolia Reputation Registry `0x8004B663…` (Draft — 온체인 사용 전 확인).
