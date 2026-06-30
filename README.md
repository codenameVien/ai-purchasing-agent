# AI Purchasing Agent

벤치마크 점수로 사용자 요청에 가장 맞는 AI 모델을 고르고, **x402 + ERC-3009** 마이크로페이먼트로 호출당 결제해 결과를 받아오는 구매 에이전트. (확장: 결과가 나쁘면 **ERC-8004** 평판 레지스트리에 기록.)

목표: 포트폴리오/해커톤 데모. Base Sepolia 테스트넷에서 e2e 실작동.

## 동작
```
요청 + 우선순위  →  [selector] 벤치마크 가중 스코어링  →  [catalog] 셀러 매핑
                 →  [payer] x402 결제(402→ERC-3009 서명→재요청)  →  결과
                 →  (확장) [reputation] 결과 나쁘면 ERC-8004 giveFeedback
```

판매자(seller) 2종:
- **Heurist** — 실제 x402 셀러, 오픈모델(Llama/Qwen/DeepSeek).
- **자체 x402 프록시** — 프론티어 모델(GPT/Claude)을 x402로 감쌈. 백엔드 교체식: 개발=무료 오픈모델, 최종=실제 API 키.

## 현재 상태
- ✅ **Phase 1 (완료)**: 벤치마크 선택 로직. 오프라인 실행/테스트 가능.
- ⬜ Phase 2: 자체 x402 프록시 셀러 + payer 연결 (테스트넷 실결제).
- ⬜ Phase 3: Heurist 실셀러 편입.
- ⬜ Phase 4: ERC-8004 평판 피드백 (확장).
- ⬜ Phase 5: 프록시 백엔드를 실제 Claude/OpenAI 키로 교체, 최종 데모.

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

## 빌드 시 검증 필요 (리서치 시점 미확정)
- Heurist 정확한 x402 엔드포인트·모델 id
- x402 Python 라이브러리 최신 API
- Base Sepolia x402 facilitator 주소
- AA `/free` 응답에서 `config/scores_cache.json`의 slug 정합성
