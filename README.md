# AI Purchasing Agent

벤치마크 점수로 사용자 요청에 가장 맞는 AI 모델을 고르고, **x402 + ERC-3009** 마이크로페이먼트로 호출당 결제해 결과를 받아오는 구매 에이전트. (확장: 결과가 나쁘면 **ERC-8004** 평판 레지스트리에 기록.)

목표: 포트폴리오/해커톤 데모. Base Sepolia 테스트넷에서 e2e 실작동.

## 동작
```
요청 + 우선순위  →  [selector] 벤치마크 가중 스코어링  →  [catalog] 셀러 매핑
                 →  [payer] x402 결제(402→ERC-3009 서명→재요청)  →  결과
                 →  (확장) [reputation] 결과 나쁘면 ERC-8004 giveFeedback
```

판매자(seller): **자체 x402 프록시** 1종. 모든 LLM 추론을 x402로 우리 프록시에 결제하고,
실제 모델은 `backend`(heurist/openrouter/anthropic/openai)가 수행. 개발=무료/mock, 최종=실키.

> 생태계 현실(2026): **테스트넷에서 pay-per-token LLM을 x402로 파는 제3자 셀러는 없다.**
> Heurist의 x402는 Base 메인넷에서 Mesh 에이전트 *툴*을 팔고(실 USDC), LLM 게이트웨이는
> API키 인증이라 x402 아님. 그래서 프록시가 테스트넷 x402 LLM 셀러의 유일 경로.
> 단, 버이어가 진짜 제3자 x402 402를 파싱함은 검증됨 → `python scripts/probe_real_402.py`.

## 현재 상태
- ✅ **Phase 1 (완료)**: 벤치마크 선택 로직. 오프라인 실행/테스트 가능.
- ✅ **Phase 2 (완료, mock 결제)**: x402 프록시 셀러 + payer + 지출 가드레일. **HTTP 402 핸드셰이크는 진짜**, 암호화(서명/검증)만 mock. 지갑/faucet 없이 e2e 실행.
- ✅ **Phase A (코드 완료)**: 실 x402 결제 경로. payer는 x402 v2 라이브러리 결제 세션, 셀러는 x402 미들웨어 + facilitator. 모든 심볼 설치본(x402 v2.14.0)에 import·construct 검증. **라이브 온체인 결제는 펀딩된 테스트넷 지갑 필요 → 아래 런북.**
- ✅ **Phase 4 (완료, mock 평판)**: judge(결과 품질 평가) → 나쁘면 ERC-8004 `giveFeedback` 기록. mock=로컬 원장, real=Reputation Registry(`0x8004B663…`, Base Sepolia, 지갑 필요). 전체 루프 e2e.
- ✅ **Phase 3 (정정)**: Heurist는 테스트넷 x402 LLM 셀러 아님(메인넷 툴 셀러)으로 검증 → 오픈모델은 프록시 `heurist` 백엔드로 편입. 버이어가 라이브 실 x402 402 파싱함 검증(`scripts/probe_real_402.py`).
- ⬜ Phase 5: 프록시 백엔드를 실제 Claude/OpenAI 키로 교체, 최종 데모.

## 실행 (Phase 2, mock e2e)
```bash
# 1) 셀러 프록시 기동 (별도 터미널)
X402_MODE=mock PROXY_BACKEND=mock uvicorn seller_proxy.main:app --port 8402
# 2) 에이전트 e2e: 선택 → 402 → mock 결제 → 결과
X402_MODE=mock python -m agent.main --prompt "Write binary search in Rust" --priority coding
python scripts/demo.py
```
출력: 선택 모델 + 이유, `[paid N USDC | MOCK tx 0x...]`, 결과물, 품질 평가.
mock 모드에선 모든 셀러가 로컬 프록시로 라우팅됨(실 Heurist는 실결제 필요 → Phase A).

평판 루프 보기(나쁜 결과 → ERC-8004 기록): 프록시를 `PROXY_BACKEND=mock_bad`로 띄우면 셀러가 거부 응답 → judge가 bad 판정 → `giveFeedback` 원장(`data/reputation_ledger.json`) 기록.

## 실행 (Phase A, 실 온체인 결제 — 테스트넷)
사전: `pip install "x402[evm]"`. 지갑 준비 + Base Sepolia USDC faucet([faucet.circle.com](https://faucet.circle.com)). 공개 facilitator 사용 시 CDP 키 불필요.
```bash
# .env 설정: WALLET_PRIVATE_KEY(펀딩된 테스트넷 키), X402_PAY_TO(셀러 수령 주소),
#            X402_NETWORK=eip155:84532, X402_FACILITATOR_URL=https://x402.org/facilitator

# 1) 실 셀러 프록시 (별도 터미널)
set -a; source .env; set +a
X402_MODE=real PROXY_BACKEND=mock uvicorn seller_proxy.real:app --port 8402
# 2) 실결제 에이전트: 선택 → 402 → ERC-3009 서명 → 온체인 정산 → 결과
X402_MODE=real python -m agent.main --prompt "..." --priority coding
```
출력의 tx hash를 [sepolia.basescan.org](https://sepolia.basescan.org)에서 조회해 온체인 정산 확인.
프론티어 백엔드(Phase 5)는 `PROXY_BACKEND=anthropic|openai` + 해당 키로 교체.

> CDP 호스티드 facilitator로 바꾸려면: `cdp-sdk` 설치 + `seller_proxy/real.py`의 `_cdp_create_headers()`에 JWT 헤더 함수 연결, `CDP_API_KEY_ID/SECRET` 설정.

## 실행 (Phase 1)
```bash
pip install -r requirements.txt
python -m agent.main --prompt "Write binary search in Rust" --priority coding
python -m agent.main --prompt "summarize this" --priority cheap fast
pytest tests/ -q
```
우선순위 라벨: `intelligence coding agentic cheap fast balanced` (복수 지정 가능).

`--live`로 Artificial Analysis API 실데이터 사용 (`.env`에 `AA_API_KEY` 필요). 없으면 `config/scores_cache.json` 캐시 사용.

## 구조
| 경로 | 역할 |
|------|------|
| `agent/selector.py` | AA 점수 fetch + 우선순위→가중치 정규화 스코어링 |
| `agent/catalog.py` | 모델→셀러 매핑, 우선순위 프리셋 |
| `agent/main.py` | 오케스트레이터 (요청→선택→결제→결과) |
| `agent/payer.py` | x402 클라이언트 + 테스트넷 지갑 + 지출 가드레일 *(Phase 2)* |
| `seller_proxy/` | x402-gated FastAPI 셀러 *(Phase 2)* |
| `reputation/` | ERC-8004 피드백 래퍼 *(Phase 4)* |
| `config/catalog.yaml` | 모델·셀러·가격·우선순위 가중치 |
| `config/scores_cache.json` | AA 점수 오프라인 캐시 (라이브로 교체) |

## 보안
- **테스트넷 전용. 임시 지갑 키만 `.env`에. 절대 커밋 금지** (`.gitignore`에 `.env`).
- payer 지출 가드레일: 호출당/세션 USDC 상한 (`MAX_USDC_PER_CALL`, `MAX_USDC_PER_SESSION`).

## 검증 상태
해소됨: x402 Python API(v2.14.0 introspect 검증), 네트워크 id(`eip155:84532`), Base Sepolia USDC(`0x036C…CF7e`), 공개 facilitator URL.
Heurist 라이브 검증됨: x402=메인넷 Mesh 툴(LLM 아님), LLM 게이트웨이=API키. 봉투 v1.
남음 (각 Phase에서):
- CDP facilitator JWT 헤더 wiring (`cdp-sdk`, 선택)
- AA `/free` 실응답에서 `config/scores_cache.json` slug 정합성 (`--live`)
- Heurist `qwen` 모델 id (supported-models에서 미확인)
