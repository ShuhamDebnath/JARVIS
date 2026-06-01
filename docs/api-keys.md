# Jarvis — API Keys Reference

> Last Updated: June 2026  
> Keep this file updated whenever a new key is added.  
> Never commit actual key values — use `.env.example` with placeholder values only.

---

## Keys Required by Phase

### Phase 0a (needed immediately)

| Key | Service | Free tier | Where to get | Used by |
|-----|---------|-----------|--------------|---------|
| `DEEPSEEK_API_KEY` | DeepSeek | $5 credit on signup | platform.deepseek.com | All research/writing agents |
| `OPENROUTER_API_KEY` | OpenRouter | Pay per use — very cheap | openrouter.ai | MiniMax M3/M2.7 agents |
| `ANTHROPIC_API_KEY` | Anthropic Claude | $5 credit on signup | console.anthropic.com | Claude Vision (Workflow 1) |

### Phase 0b (before Phase 1 starts)

| Key | Service | Free tier | Where to get | Used by |
|-----|---------|-----------|--------------|---------|
| `SERPER_API_KEY` | SerperDev | 2,500 free queries/month | serper.dev | SerperDev web search tool |
| `FIRECRAWL_API_KEY` | Firecrawl | 500 pages/month free | firecrawl.dev | Firecrawl scraping tool |
| `REDDIT_CLIENT_ID` | Reddit API | Free | reddit.com/prefs/apps → create app | PRAW Reddit tool |
| `REDDIT_CLIENT_SECRET` | Reddit API | Free | Same as above | PRAW Reddit tool |
| `REDDIT_USER_AGENT` | Reddit API | Free | Set to: `jarvis/1.0 by /u/yourusername` | PRAW Reddit tool |

### Phase 5 (before voice layer)

| Key | Service | Free tier | Where to get | Used by |
|-----|---------|-----------|--------------|---------|
| `PORCUPINE_ACCESS_KEY` | Picovoice | Free tier available | console.picovoice.ai | Wake word — "Hey Jarvis" |

---

## Services With No API Key (free, no auth)

| Service | Tool | Notes |
|---------|------|-------|
| Google Trends | pytrends | No key — scrapes Google Trends directly |
| App Store | app-store-scraper (npm) | No key — public data |
| Play Store | google-play-scraper (npm) | No key — public data |
| ntfy.sh | ntfy push notifications | No key — use a unique topic name as your "key" |
| Kokoro TTS | kokoro-onnx | Runs locally — no key |
| Faster-Whisper | faster-whisper | Runs locally — no key |

---

## Key Setup Instructions

### DeepSeek
1. Go to platform.deepseek.com
2. Create account
3. Go to API Keys section
4. Create new key — name it `jarvis`
5. Copy to `.env`: `DEEPSEEK_API_KEY=sk-...`

**Note:** DeepSeek routes through OpenRouter in this project. You can use either:
- Direct DeepSeek key (`DEEPSEEK_API_KEY`) with base URL `https://api.deepseek.com`
- OpenRouter key (`OPENROUTER_API_KEY`) with model string `deepseek/deepseek-chat`

CrewAI config in `agents.yaml` uses the OpenRouter routing — so `OPENROUTER_API_KEY` is the one that must be set.

### OpenRouter
1. Go to openrouter.ai
2. Create account — add $5–10 credit (lasts weeks at DeepSeek rates)
3. Go to Keys → Create Key — name it `jarvis`
4. Copy to `.env`: `OPENROUTER_API_KEY=sk-or-...`

### Anthropic
1. Go to console.anthropic.com
2. Create account — free $5 credit
3. Go to API Keys → Create Key — name it `jarvis`
4. Copy to `.env`: `ANTHROPIC_API_KEY=sk-ant-...`

### SerperDev
1. Go to serper.dev
2. Create account — 2,500 free queries/month (no credit card)
3. Go to Dashboard → API Key
4. Copy to `.env`: `SERPER_API_KEY=...`

### Firecrawl
1. Go to firecrawl.dev
2. Create account — 500 free pages/month
3. Go to Dashboard → API Key
4. Copy to `.env`: `FIRECRAWL_API_KEY=fc-...`

### Reddit (PRAW)
1. Go to reddit.com — log in
2. Go to reddit.com/prefs/apps
3. Scroll to bottom → click "create another app"
4. Fill in:
   - Name: `jarvis`
   - Type: `script`
   - Redirect URI: `http://localhost:8080`
5. Click Create App
6. Copy `client_id` (under the app name) and `secret`
7. Add to `.env`:
   ```
   REDDIT_CLIENT_ID=your_client_id
   REDDIT_CLIENT_SECRET=your_secret
   REDDIT_USER_AGENT=jarvis/1.0 by /u/your_reddit_username
   ```

### Porcupine (Picovoice) — Phase 5 only
1. Go to console.picovoice.ai
2. Create account — free tier allows 1 wake word
3. Go to AccessKey → Create
4. Copy to `.env`: `PORCUPINE_ACCESS_KEY=...`

---

## .env.example (copy of current template)

```
# ─── LLM ───
OPENROUTER_API_KEY=your_openrouter_key_here
ANTHROPIC_API_KEY=your_anthropic_key_here

# ─── Research tools ───
SERPER_API_KEY=your_serper_key_here
FIRECRAWL_API_KEY=your_firecrawl_key_here

# ─── Reddit (PRAW) ───
REDDIT_CLIENT_ID=your_reddit_client_id
REDDIT_CLIENT_SECRET=your_reddit_client_secret
REDDIT_USER_AGENT=jarvis/1.0 by /u/your_reddit_username

# ─── Voice (Phase 5 only — leave blank until then) ───
PORCUPINE_ACCESS_KEY=

# ─── Monitoring ───
NTFY_TOPIC=jarvis-alerts-your-unique-name

# ─── Cost guard ───
MAX_TOKENS_PER_RUN=200000

# ─── Reddit monitor config ───
REDDIT_TRACKED_SUBREDDITS=androiddev,FlutterDev,iOSProgramming,mobiledev,india
REDDIT_TRACKED_KEYWORDS=habit tracker,productivity app,flutter,swift
REDDIT_YOUR_APP_NAME=YourAppName

# ─── Briefing config ───
TRACKED_CATEGORIES=productivity,health,education,utilities
TRACKED_KEYWORDS=flutter,swift,react native,mobile app india
```

---

## Cost Tracking

Target: under ₹2,000/month total.

| Service | Free tier | Estimated monthly usage | Estimated monthly cost |
|---------|-----------|------------------------|----------------------|
| OpenRouter (DeepSeek) | Pay per use | ~2M tokens/month | ~₹300–600 |
| OpenRouter (MiniMax M3) | Pay per use | ~500k tokens/month | ~₹200–400 |
| Anthropic Claude | Pay per use | ~200k tokens/month (vision only) | ~₹200–400 |
| SerperDev | 2,500 free/month | ~1,000 queries/month | ₹0 (within free tier) |
| Firecrawl | 500 pages/month free | ~300 pages/month | ₹0 (within free tier) |
| Reddit API | Free | Unlimited | ₹0 |
| Porcupine | Free tier | Continuous local | ₹0 |

**Total estimated monthly cost: ₹700–1,400** — well within ₹2,000 target.

---

*End of API Keys Reference*
