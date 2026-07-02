"""Interactive, LOCAL key setup — you paste keys into your own terminal, they go
straight to .env, and are never shown to anyone (getpass hides input).

For each key you'll see WHERE to get it and WHY it's needed. Press Enter to skip
any you don't have yet. Run again anytime to add more.

  python scripts/setup_keys.py
"""
import getpass
import os
import sys

ROOT = os.path.dirname(os.path.dirname(__file__))
ENV = os.path.join(ROOT, ".env")

# (env var, why, where to get it, is_secret)
KEYS = [
    ("OPENROUTER_API_KEY",
     "Real model answers for a FREE cost — open models via OpenRouter free tier.",
     "https://openrouter.ai/keys  (sign in → Create Key). Free tier covers ':free' models.",
     True),
    ("GEMINI_API_KEY",
     "Real Gemini answers (Google). Generous FREE tier.",
     "https://aistudio.google.com/apikey  (Create API key). Free tier available.",
     True),
    ("ANTHROPIC_API_KEY",
     "Real Claude answers (frontier). Paid per token.",
     "https://console.anthropic.com/settings/keys",
     True),
    ("OPENAI_API_KEY",
     "Real GPT answers (frontier). Paid per token.",
     "https://platform.openai.com/api-keys",
     True),
    ("AA_API_KEY",
     "Live benchmark scores (--live) instead of the cached fixture.",
     "https://artificialanalysis.ai/  (Data API, free tier 1000 req/day).",
     True),
    ("WALLET_PRIVATE_KEY",
     "Live on-chain x402 payment. TESTNET key ONLY — never a real/funded wallet.",
     "Generate a throwaway with:  python scripts/gen_wallet.py   then fund it at faucet.circle.com",
     True),
]


def _read_env() -> dict[str, str]:
    vals: dict[str, str] = {}
    if os.path.exists(ENV):
        for line in open(ENV, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                vals[k.strip()] = v
    return vals


def _write_env(vals: dict[str, str]) -> None:
    lines = ["# managed by scripts/setup_keys.py — NEVER commit (gitignored)"]
    lines += [f"{k}={v}" for k, v in vals.items()]
    with open(ENV, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    os.chmod(ENV, 0o600)


def main() -> int:
    print("Local key setup. Input is hidden and written only to .env (gitignored).\n")
    vals = _read_env()
    for name, why, where, secret in KEYS:
        have = " (already set)" if vals.get(name) else ""
        print(f"● {name}{have}\n    why:   {why}\n    where: {where}")
        prompt = f"    paste {name} (Enter to skip): "
        entered = (getpass.getpass(prompt) if secret else input(prompt)).strip()
        if entered:
            # getpass hides input, so users often paste twice -> exact duplicate. auto-fix.
            if len(entered) % 2 == 0 and entered[: len(entered) // 2] == entered[len(entered) // 2:]:
                entered = entered[: len(entered) // 2]
                print("    ⚠ 중복 입력 감지 → 자동으로 한 번만 저장")
            vals[name] = entered
            mask = f"{entered[:4]}…{entered[-4:]}" if len(entered) > 8 else "****"
            print(f"    ✓ 저장됨 ({len(entered)}자, {mask})\n")   # 값 안 보이게, 들어간 건 확인
        else:
            print("    – skipped\n")
    _write_env(vals)
    print(f"Done. Wrote {ENV} (chmod 600). Keys were never displayed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
