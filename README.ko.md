<div align="center">

[![English](https://img.shields.io/badge/README-English-lightgrey?style=for-the-badge)](README.md)&nbsp;&nbsp;[![한국어](https://img.shields.io/badge/README-한국어-2ea44f?style=for-the-badge)](README.ko.md)

</div>

# AI 구매 에이전트 — x402 모델 마켓플레이스

자연어로 말하면, 에이전트가 **마켓플레이스에서 최적 셀러를 고르고**(벤치마크 점수 + 가격 + 속도 + 평판), **x402 + ERC-3009 마이크로페이먼트로 호출당 결제**해 **진짜 모델 답변**을 받아오며, **ERC-8004 평판**(너의 👍/👎 포함)을 기록해 나쁜 셀러가 다음엔 밀리게 한다.

> ✅ **라이브 검증됨.** Base Sepolia 실 온체인 x402 결제 ([tx `0xabb329c2…`](https://sepolia.basescan.org/tx/0xabb329c2e454ea8f81bb964786a08fabffbad16afd052b0a7360c4a0cfb6b7a3), 가스리스 USDC 이동). 진짜 답변: **OpenRouter**(Llama/DeepSeek/Qwen) + **Google Gemini**(2.5 Flash).

📐 구성도+시퀀스: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) · 로드맵: [docs/ROADMAP.md](docs/ROADMAP.md) · 키/지갑: [docs/HANDOFF.md](docs/HANDOFF.md)

---

## 무엇을 하나

```
자연어 요청  ("러스트로 이진탐색 짜줘", "빠르고 저렴하게")
  → [nl_priority] 프롬프트에서 우선순위 추론(coding / cheap / fast …)
  → [selector]    오퍼를 벤치마크 × 우선순위로 스코어링 + 평판 반영
  → [payer]       x402: 402 → ERC-3009 서명 → 재요청 → 정산
  → [backend]     진짜 추론 (OpenRouter / Gemini / …)
  → [judge]       기계 배달체크(빈값/거부/에러) ── 품질은 사람 몫
  → [reputation]  사람 👍/👎 (scripts/rate.py) → 다음 선택에 반영
```

**왜 이 구조인가.** AI가 종량제로 가면 경쟁력은 *맞는 모델+셀러를 골라 효율적으로 사 쓰는 것*. x402가 고정수수료 없는 마이크로페이먼트를 에이전트 자율(M2M)로 가능케 한다. 이 프로젝트는 그 시장의 구매자 측.

## 마켓플레이스 (모델이 아니라 오퍼)

**카탈로그 항목 = 오퍼** = *셀러 하나가 모델 하나를 파는 것*. **같은 오픈모델을 셀러 여럿이** 팔며 **가격·속도로 경쟁**하고, **평판**(피드백으로 학습)이 시간이 지나며 승자를 바꾼다.

```
같은 Llama 3.3, 셀러 3명:   gamma $0.0012 / 35tps   (최저가, 느림)
                            beta  $0.0015 / 60tps
                            alpha $0.0020 / 90tps   (비쌈, 최고속)
"cheap" → gamma   "fast" → alpha   gamma가 부정직(👎) → 다음엔 → beta
```

**프록시 하나가 진짜 모델을 대행.** 2026년 현재 테스트넷에 pay-per-token LLM을 x402로 파는 제3자가 없어, 모든 추론은 x402로 우리 프록시에 결제하고 실제 모델은 교체식 `backend`(`openrouter_free`·`gemini`·`heurist`·`anthropic`·`openai`·`mock`)가 수행. 구매자는 **오퍼를 실시간 조회**도 가능: `GET /marketplace`.

## 실행 (mock — 키 불필요, 오프라인)

```bash
cd ~/ai-purchasing-agent
pip install -r requirements.txt
pytest -q                                       # 33 테스트

# 터미널1: x402 프록시 (암호화 mock, 백엔드 mock)
cd ~/ai-purchasing-agent
X402_MODE=mock PROXY_BACKEND=mock uvicorn seller_proxy.main:app --port 8402
# 터미널2:
cd ~/ai-purchasing-agent
X402_MODE=mock python -m agent.main --prompt "빠르고 저렴하게 요약해줘"   # 자연어→선택→결제→검수
curl -s localhost:8402/marketplace | python3 -m json.tool                # 오퍼 조회
python scripts/rate.py gamma down                                        # 사람 👎 → 다음 회피
python scripts/spend.py                                                  # 지출 요약
```

## 실행 (진짜 답변 — 키 1개)

```bash
cd ~/ai-purchasing-agent && python scripts/setup_keys.py    # 로컬 숨김 입력 → .env
#   OpenRouter(무료티어)로 오픈모델; Gemini 무료티어는 GEMINI_API_KEY
cd ~/ai-purchasing-agent && set -a; . ./.env; set +a
uvicorn seller_proxy.main:app --port 8402                   # PROXY_BACKEND 비우면 모델별 라우팅
# 터미널2:
cd ~/ai-purchasing-agent && set -a; . ./.env; set +a
python -m agent.main --prompt "빠르게: 블록체인 한 문장 설명"   # → Gemini/OpenRouter 진짜 답변
```

## 실행 (라이브 온체인 결제 — Base Sepolia)

```bash
cd ~/ai-purchasing-agent
pip install "x402[evm]"
python scripts/gen_wallet.py         # 일회용 지갑 → .env, BUYER 주소를 faucet.circle.com에서 충전
cd ~/ai-purchasing-agent && set -a; . ./.env; set +a
uvicorn seller_proxy.real:app --port 8402                   # X402_MODE=real
# 터미널2: python -m agent.main --prompt "..." --priority coding
```
tx는 [sepolia.basescan.org](https://sepolia.basescan.org)에서 정산 확인. 공개 facilitator라 **CDP 키 불필요**, 가스 대납. payer가 **실제 402 금액**으로 상한 검사, 초과 시 서명 전 거부.

## 프로젝트 구조

| 경로 | 역할 |
|------|------|
| `agent/nl_priority.py` | 자연어 프롬프트 → 우선순위 라벨 (룰; LLM 스텁) |
| `agent/selector.py` | 벤치마크 × 우선순위 스코어링(오퍼 대상) + 평판 factor |
| `agent/catalog.py` | 오퍼(셀러×모델); yaml 또는 `/marketplace`에서 로드 |
| `agent/discovery.py` | 마켓 엔드포인트서 오퍼 실시간 조회 |
| `agent/payer.py` | x402 클라이언트(mock + real `x402[evm]`) + 지출 가드레일 + 에러 |
| `agent/judge.py` | 기계 배달체크 (품질 심판 아님) |
| `agent/accounting.py` | 지출 원장 + 요약 |
| `agent/main.py` | 오케스트레이터 (요청→추론→선택→결제→답변→검수→피드백) |
| `seller_proxy/main.py` | mock x402 셀러 + `GET /marketplace` |
| `seller_proxy/real.py` | real x402 셀러 (x402 v2 미들웨어 + facilitator) |
| `seller_proxy/backends.py` | provider-agnostic 백엔드(openrouter/gemini/heurist/anthropic/openai/mock) |
| `reputation/feedback.py` | ERC-8004 giveFeedback + `load_reputation`(사람 가중) |
| `scripts/` | `setup_keys.py` · `gen_wallet.py` · `rate.py`(👍/👎) · `spend.py` · `demo.py` · `probe_real_402.py` |

## 상태

- ✅ 벤치마크 선택 · 자연어 우선순위 · 다중셀러 마켓(가격/속도/평판) · discovery 엔드포인트
- ✅ x402 결제(mock + **real, Base Sepolia 라이브 검증**) · 실제 금액 가드레일
- ✅ 진짜 답변(OpenRouter + Gemini, 라이브) · 배달체크 · 사람 👍/👎 → 평판 루프 · 지출 회계
- ⬜ 온체인 giveFeedback · LLM 우선순위 추론 · 객관 검증(코드=테스트) — `docs/ROADMAP.md`

## 보안

- **테스트넷 + 일회용 지갑만.** 개인키는 모든 체인을 통제 — 메타마스크/메인넷/자산 든 키를 `.env`에 절대 금지. `scripts/setup_keys.py`는 숨김 로컬 입력; `.env`는 gitignore + 커밋 안 됨(검증: 히스토리에 시크릿 없음).
- 지출 가드레일: `MAX_USDC_PER_CALL` / `MAX_USDC_PER_SESSION`, 실제 402 금액 기준.
- **API 키를 채팅/스크린샷에 절대 노출 금지** — 노출되면 폐기·재발급.

## 검증된 사실 (리서치 + 라이브, 추측 아님)

- x402 Python v2.14.0 (`eip155:84532` CAIP-2). Base Sepolia USDC `0x036CbD…CF7e`; 공개 facilitator `https://x402.org/facilitator`.
- Heurist x402 = 메인넷 Mesh 툴, 테스트넷 LLM 셀러 아님(라이브 curl).
- Gemini 현행 모델 `gemini-2.5-flash`(2.0 은퇴; models API로 검증). 키 형식 `AQ.…`.
- ERC-8004 `giveFeedback(...)` + Base Sepolia Reputation Registry `0x8004B663…` (Draft — 온체인 전 확인).
