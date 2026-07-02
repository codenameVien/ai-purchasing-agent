# 추후 작업 (Roadmap / TODO)

데모(개념 증명)는 완료. 아래는 **실서비스로 키울 때** 필요한 확장. teardown 하며 발견한 항목 누적.

---

## A. payer (결제) — mock이 가린 실전 갭

우선순위 = 급한 불 순서.

### 1순위 — 정확성 (지금도 살짝 버그)
- [x] **실제 금액 상한 체크** ✅ `_extract_requirements`+`_required_usdc`로 402의 실제 금액 파싱(mock=body 달러, real=PAYMENT-REQUIRED 헤더 atomic). mock·real 둘 다 서명 전 상한 검사, 영수증도 실제 금액. 검증: real 상한 0.0005<0.001 → 서명 전 거부.
- [x] **결제 전 잔액 확인** ✅ `_precheck_balance`: 서명 전 지갑 USDC 잔액(ERC-20 balanceOf) 조회 → 부족하면 `PaymentError`로 조기 중단(faucet 안내). 못 읽으면 best-effort로 진행(정산이 최종 게이트).

### 2순위 — 신뢰성
- [x] **tx 확정 대기** ✅ `_wait_for_confirmation`: 200을 최종으로 안 믿음. tx receipt 폴링(status=1 확인/revert=실패/타임아웃). 영수증 `confirmed` 필드 + CLI 표시. `X402_WAIT_CONFIRM=0`으로 opt-out, `X402_CONFIRM_TIMEOUT` 조정.
- [~] **에러 처리** ✅ real 경로 명확한 에러(PaymentError: 잔액부족/검증실패·셀러/facilitator 에러) + 5xx 재시도 1회. ⬜ 남음: facilitator 폴백, 봉투 v1/v2 자동 협상.

### 3순위 — 운영
- [x] **회계/영수증 저장** ✅ `agent/accounting.py` 지출 원장 + `scripts/spend.py` 요약(총액·셀러별·모델별). 매 결제 기록.
- [ ] **키 관리**: `.env` 평문(일회용 테스트넷이라 OK) → 실자금은 KMS/시크릿볼트/HSM. (`scripts/setup_keys.py`로 로컬 안전 입력)
- [ ] **동시성/지갑 풀**: 단일 지갑·순차 가정. 병렬 결제 시 nonce 충돌 방지, 지갑 풀·자동 충전.

---

## B. selector (선택) — 자연어 우선순위

- [x] **NL 프롬프트 → 우선순위 자동 추론 (룰 기반)** ✅ `agent/nl_priority.py`. 키워드 매칭(KR+EN)으로 자연어→우선순위. `--priority` 생략 시 prompt에서 추론. 데모: "Rust 코드"→coding, "빠르고 저렴"→cheap+fast.
- [x] **LLM 기반 추론으로 업그레이드** ✅ `infer_priorities(mode="llm")` 구현. `agent/llm.py`(buyer-side LLM, Gemini/OpenRouter/OpenAI, x402 아님)로 의도 분류. `--infer llm`. 키 없거나 실패 시 룰로 fallback(오프라인 동작 유지). 유효 라벨만·순서 보존·dedup.

---

## C. catalog (마켓플레이스) — 정적 → 동적

3레벨. 아래로 갈수록 큼.

- [~] **레벨 1 (부분 완료)**: 동적 카탈로그. ✅ 프록시 `GET /marketplace`(오퍼+평판) + `agent/discovery.py`로 구매자가 하드코딩 대신 시장 실시간 조회(`--marketplace URL`). 데모: 8오퍼 조회→선택. ⬜ 남음: AA API 라이브 모델목록으로 오퍼 자동생성(키 필요).
- [~] **레벨 2 (부분 완료)**: 다중 셀러 시뮬. ✅ 오퍼(셀러×모델) 구조, 같은 오픈모델 셀러 여럿이 다른 가격·속도에. 선택=최적 오퍼, 평판=셀러별. 셀러가 **가격+속도로 경쟁**(오퍼별 speed_tps). 라이브: cheap→gamma(느림), fast→alpha(빠름); 먹튀→평판 강등→정직 셀러로. ⬜ 남음: 셀러 각자 프로세스(현재 한 프록시가 대행), discovery 레지스트리, uptime/신뢰도 지표.
- [ ] **레벨 3 (큼, ~1주+)**: 온체인 리스팅. ERC-8004 Identity Registry를 마켓 등록부로. 셀러 온체인 등록 + 온체인 평판까지 봐서 선택. 완전 탈중앙.

권장: 레벨1 → 레벨2 순.

---

## D. seller_proxy (판매자) 확장

- [ ] **모델별 동적 가격**: real 프록시는 라우트 1개·가격 1개 고정. 모델마다 다른 가격·라우트 지원.
- [ ] **CDP facilitator 연결**: `_cdp_create_headers()` 스텁 → cdp-sdk로 JWT 헤더 실제 연결(메인넷·엔터프라이즈용).
- [~] **판매자측 보호**: ✅ 입력 검증(messages 없으면 400, 잘못된 JSON 거부). ⬜ 남음: 레이트리밋, 백엔드 인증, 판매자 수익 집계.
- [ ] **다중 모델 한 프록시**: 지금 한 프록시=한 백엔드. 한 프록시가 여러 모델 서빙(라우트 분기).

## F. 감사/검증 (독립 제3자 셀러 신뢰 — 완성형 마켓 전제)

> 전제: MVP는 셀러=우리 프록시 1개(못 속임). 아래는 **남이 운영하는 독립 셀러**가 마켓에 들어온 뒤(레벨2 다중셀러) 성립하는 신뢰 문제. 단순 저품질·과금부풀리기는 이미 judge+평판+SpendGuard가 상쇄 → 아래는 그걸로 안 풀리는 것.

- [ ] **A. 모델 바꿔치기 탐지**: 셀러가 "Claude" 팔며 싼 Llama 응답. → 챌린지 프롬프트(모델별 지문), 확률적 재검증·다수 셀러 교차대조, (심화)TEE/실행 증명 attestation.
- [ ] **B. 결제-전달 비원자성(먹튀) 완화**: 선불 정산 후 미전달/쓰레기. → 에스크로·조건부 정산(결과 검증 후 릴리스), 분쟁 환불 컨트랙트, ERC-8004 Validation Registry로 미전달 증명.
- [ ] **C. 판정자·평판 자체 신뢰(메타)**: 거짓 평판 저격(griefing)·judge 속임. → ERC-8004 Validation Registry(검증자·TEE), 스테이킹·다수결.

## G. 검수·평가 전략 (judge 역할 재정의)

> 결론: **AI가 품질 심판 ❌**(지금 시대 순환·불신). **사람 좋아요/싫어요 → 평판 ⭕**. 단 per-call 게이트 아니라 **사후 비동기**(우버 별점처럼) — 자율 M2M 유지.

- [x] **judge 축소** ✅ 배달 체크(기계 필터)로 역할 재정의(docstring). 품질심판 아님 명시. LLM 모드는 의도적 스텁.
- [x] **품질 평가 = 사람 피드백(좋아요/싫어요)** ✅ `scripts/rate.py <seller> up|down` → reputation(source="human"). 사후 비동기(우버 별점). 데모: 사람 👎 gamma → 다음 선택서 gamma 회피. 피드백에 source(auto/human) 구분.
- [x] **객관 검증 우선** ✅ `agent/verify.py` + `judge(mode="objective")`. 검증 가능 태스크는 기계적 참/거짓: 코드=`compile()` 문법검증(안전, 무실행) + `VERIFY_EXECUTE=1` opt-in 실행(subprocess+timeout, 위험 명시), 수학=검산. 검증 불가면 배달 heuristic으로 fallback. 데모: 안 컴파일되는 긴 코드 답변 → 길이 heuristic은 통과해도 objective는 bad.
- [ ] **사람 = 감독층**(전수 아님): 샘플링·분쟁해결·자동필터 보정. per-call 검수공 아님.
- 참고: 검수(judge, 이번 결과) ≠ 감사(reputation, 셀러 이력). 검수는 감사에 넣을 신호 생성기.

## H. reputation (감사/평판) 확장

- [x] **평판 → selector 반영 (루프 완성)** ✅ 구현됨. `load_reputation()`이 원장 집계 → `select(reputation=..., reputation_weight=)`가 factor 적용해 나쁜 셀러 하락. 라이브 데모: 1회차 bad → 2회차 그 셀러 점수 하락. (default weight 0.5 = 수정자, 높이면 winner flip)
- [~] **온체인 giveFeedback 실구현** ✅ 코드+테스트 완성 `_give_feedback_real`: web3로 `giveFeedback(uint256 agentId,int128 value,uint8 valueDecimals,string tag1,string tag2,string endpoint,string feedbackURI,bytes32 feedbackHash)` build→sign→send. **ABI 실검증**(erc-8004/erc-8004-contracts `abis/ReputationRegistry.json`, 레포에 저장). msg.sender=buyer=client, 컨트랙트가 self-feedback 차단 → 결제자가 피드백 = 정확. 테스트는 web3 mock(실 broadcast 없음). `REPUTATION_MODE=real`에서만 발동(기본 mock). 미등록 셀러는 명확히 차단(tokenId 위조 불가).
- [x] **셀러 Identity 등록 도구** ✅ `reputation/identity.py` `register_agent`(ERC-8004 Identity Registry `register()`/`register(agentURI)`, ABI 실검증, `Registered` 이벤트로 tokenId 파싱) + `scripts/register_seller.py`. gen_wallet이 `SELLER_PRIVATE_KEY`(buyer와 분리, self-feedback 차단 만족) 발급. 테스트 web3 mock. ⬜ 남음(실 broadcast): 셀러 지갑에 Base Sepolia ETH(가스) 충전 후 등록 실행 → `SELLER_AGENT_IDS` 매핑. **되돌릴 수 없는 온체인 tx = 사용자 승인 후.**
- [x] **입력원 = 사람 좋아요/싫어요** ✅ `scripts/rate.py`로 사람 👍/👎(source="human"). judge(auto)는 배달실패만. 둘 다 같은 reputation으로. (UI화·human 가중은 남음)

## E. 기타 (teardown 진행하며 추가 예정)

- (Part 8~ 진행하며 발견 항목 여기 누적)
