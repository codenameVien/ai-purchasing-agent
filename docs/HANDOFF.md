# 다음 — 네 손이 필요한 것 (Handoff)

여기까지는 **키·지갑 없이** 다 구현·검증됨(mock/테스트넷 구조). 아래는 **네가 데스크탑에서 키/지갑을 넣어야** 풀리는 것들. 순서·위치·방법 정리.

---

## 0. 한 번에 키 넣기 (안전, 로컬)

```bash
cd ~/ai-purchasing-agent
python scripts/setup_keys.py
```
- 입력은 **숨겨지고 `.env`(gitignore)에만** 저장 — 아무한테도 안 보임.
- 각 키의 **용도 + 받는 곳**이 화면에 뜸. 없는 건 Enter로 건너뜀. 언제든 다시 실행.

---

## 1. 진짜 모델 답변 (지금은 mock echo)

**필요**: API 키 1개. 가장 싼 길 = **무료 OpenRouter 키($0)**.
- 받는 곳: https://openrouter.ai/keys (로그인 → Create Key). `:free` 모델은 공짜.
- 넣기: `setup_keys.py`에서 `OPENROUTER_API_KEY` 입력.
- 실행:
  ```bash
  # 두 터미널 모두 먼저: cd ~/ai-purchasing-agent && set -a; . ./.env; set +a
  # 프록시: PROXY_BACKEND 비우면 모델별 backend로 라우팅
  cd ~/ai-purchasing-agent && set -a; . ./.env; set +a
  uvicorn seller_proxy.main:app --port 8402          # 터미널1
  # 터미널2 (새 창):
  cd ~/ai-purchasing-agent && set -a; . ./.env; set +a
  python -m agent.main --prompt "explain TLS" --priority cheap   # 오픈모델 진짜 답변
  ```
- 프론티어(Claude/GPT) 진짜 답변은 `ANTHROPIC_API_KEY`/`OPENAI_API_KEY` (유료).

## 2. 라이브 온체인 결제 (이미 1회 검증됨, 재현용)

**필요**: 펀딩된 **테스트넷 지갑**.
```bash
cd ~/ai-purchasing-agent
pip install "x402[evm]"
python scripts/gen_wallet.py       # 일회용 지갑 2개 생성 → .env
#  → 출력된 BUYER 주소를 https://faucet.circle.com (Base Sepolia)에서 USDC 충전

# 터미널1:
cd ~/ai-purchasing-agent && set -a; . ./.env; set +a
uvicorn seller_proxy.real:app --port 8402
# 터미널2 (새 창):
cd ~/ai-purchasing-agent && set -a; . ./.env; set +a
python -m agent.main --prompt "Write binary search in Rust" --priority coding
```
- tx hash를 https://sepolia.basescan.org 에서 확인. 공개 facilitator라 CDP 키 불필요.
- ⚠️ 메타마스크/실자금 키 절대 금지. 일회용 테스트넷만.

## 3. 온체인 평판 (지금은 로컬 원장)

**필요**: 지갑 + 셀러 ERC-721 등록. `reputation/feedback.py::_give_feedback_real` 스텁 구현 필요.
- `REPUTATION_MODE=real` + web3 컨트랙트 호출(ERC-8004 Reputation Registry `0x8004B663…`). ABI Draft라 확인 필요.

## 4. LLM 우선순위 추론 (지금은 키워드 룰)

**필요**: API 키. `agent/nl_priority.py::infer_priorities(mode="llm")` 스텁 구현.

---

## 지금 상태 (키 없이 이미 되는 것)

```bash
# 모든 명령은 먼저: cd ~/ai-purchasing-agent
cd ~/ai-purchasing-agent
pytest -q                                   # 33 tests

# mock 전체 흐름 (지갑·키 0) — 터미널1:
cd ~/ai-purchasing-agent
X402_MODE=mock PROXY_BACKEND=mock uvicorn seller_proxy.main:app --port 8402
# 터미널2 (새 창):
cd ~/ai-purchasing-agent
X402_MODE=mock python -m agent.main --prompt "빠르고 저렴하게 요약"   # 자연어→선택→결제→검수
curl -s localhost:8402/marketplace | python3 -m json.tool            # 시장 오퍼 조회
python scripts/rate.py gamma down                                    # 사람 👎 → 다음 선택서 회피
python scripts/spend.py                                              # 지출 요약
```

구현·검증된 것: 자연어 선택 · 다중셀러(가격·속도 경쟁) · x402 결제(mock+real 구조, 라이브 1회 성공) · 실제금액 상한 · 검수(배달체크) · 사람 평판(human 가중) · 마켓 discovery · 지출회계 · 에러처리. 전체 로드맵은 `docs/ROADMAP.md`.
