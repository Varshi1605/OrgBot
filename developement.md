

# Development Workflow — SDD Approach


## HFT Platform — AI Trading Assistant


> This document outlines the complete step-by-step development workflow followed using the **Software Design Document (SDD)** approach.


---


## Phase 1: Planning & Design


### Step 1 — Define Requirements


- [x] Identify application type: Question & Answer Chatbot UI
- [x] Select framework: React 19 + Vite 8
- [x] Define target platforms: Desktop, Tablet, Mobile (responsive)
- [x] Identify core features:
 - Conversational message interface with HFT domain context
 - Collapsible conversation history sidebar
 - Welcome screen with HFT-specific suggested prompts
 - Dual dark/light theme with localStorage persistence
 - Typing indicator animation
 - Auto-scrolling chat window
 - Keyboard shortcut support


### Step 2 — Create Software Design Document


- [x] Author [docs/SDD.md](../docs/SDD.md)
- [x] Define component hierarchy and responsibilities
- [x] Specify data models (Message, Conversation)
- [x] Document state management strategy (`useChat` hook)
- [x] Establish design tokens (colors, radii, shadows)
- [x] Define responsive breakpoints (mobile, tablet, desktop)
- [x] Outline animation specifications


---


## Phase 2: Project Setup


### Step 3 — Scaffold Project


```bash
npx create-vite@latest . --template react
```


- [x] Initialize React project with Vite
- [x] Install dependencies (`react`, `react-dom`, `vite`, `eslint`)
- [x] Verify project structure


### Step 4 — Configure Project Metadata


- [x] Update `index.html` — Title, meta description, Google Fonts (Inter)
- [x] Update `package.json` — Project name `team-12`
- [x] Set up `.gitignore` for node_modules, dist, IDE files


---


## Phase 3: Implementation


### Step 5 — Global Styles & Design Tokens


- [x] `src/index.css` — CSS Custom Properties (40+ design tokens), dual dark/light theme, reset, typography
- [x] `src/App.css` — Root layout (flexbox full-height), sidebar collapse states


### Step 6 — Utility Layer


- [x] `src/utils/formatTime.js` — Relative time formatting, message timestamps
- [x] `src/constants/botResponses.js` — HFT domain mock responses, trading-specific suggested prompts


### Step 7 — State Management


- [x] `src/hooks/useChat.js` — Custom hook managing:
 - Conversation CRUD (create, read, update, delete)
 - Message sending with simulated bot responses
 - Typing indicator state
 - Active conversation tracking
- [x] `src/hooks/useTheme.js` — Custom hook managing:
 - Dark/light theme toggle
 - localStorage persistence (key: `hft-theme`)
 - `data-theme` attribute on `<html>` element


### Step 8 — Atomic Components


- [x] `Avatar` — SVG-based user/bot avatars with role-based styling
- [x] `TypingIndicator` — Three-dot bounce animation


### Step 9 — Message Components


- [x] `MessageBubble` — Aligned message rendering with avatar, timestamp
- [x] `WelcomeScreen` — Empty state with greeting and clickable suggestion cards


### Step 10 — Layout Components


- [x] `ChatHeader` — Bot identity, online status, latency badge, theme toggle
- [x] `ChatInput` — Auto-resize textarea, gradient send button, keyboard handling
- [x] `ChatWindow` — Scrollable container, auto-scroll to bottom, empty state fallback
- [x] `ChatLayout` — Composition of Header + Window + Input


### Step 11 — Navigation Component


- [x] `Sidebar` — Conversation list, new chat button, delete action, collapsible to icon-only mode


### Step 12 — Root Composition


- [x] `App.jsx` — Wire Sidebar + ChatLayout with useChat/useTheme hooks, sidebar collapse state


---


## Phase 4: Quality Assurance


### Step 13 — Build Verification


```bash
npm run build
```


- [x] Production build succeeds (0 errors)
- [x] All 38 modules transformed
- [x] Bundle sizes verified:
 - CSS: ~10.9 KB (gzipped: ~2.5 KB)
 - JS: ~202.8 KB (gzipped: ~63.8 KB)


### Step 14 — Lint Check


```bash
npm run lint
```


- [x] ESLint passes with no errors


---


## Phase 5: Documentation


### Step 15 — Project Documentation


- [x] `README.md` — Setup instructions, feature list, project structure
- [x] `docs/SDD.md` — Complete Software Design Document
- [x] `docs/DEVELOPMENT_STEPS.md` — This file


---


## Phase 6: Version Control & Deployment


### Step 16 — Git Commit & Push


#### Stage all files:


```bash
git add .
```


#### Commit with conventional commit message:


```bash
git commit -m "feat: implement HFT Platform UI with React + Vite


- Set up React 19 project with Vite 8 build tooling
- Build professional HFT trading platform interface
 - Dual dark/light theme system (dark-first, localStorage persist)
 - Collapsible sidebar with CSS-driven icon-only mode
 - ChatHeader with theme toggle, latency badge, status indicator
 - ChatWindow with auto-scrolling message container
 - MessageBubble with gradient user bubbles and dark bot cards
 - ChatInput with gradient send button and glow focus ring
 - WelcomeScreen with HFT-branded suggestion cards
 - TypingIndicator with animated bounce effect
 - Avatar component with SVG-based role icons
- Create custom hooks for state management
 - useChat: conversation CRUD, simulated bot responses
 - useTheme: theme toggle with localStorage persistence
- Establish design system with 40+ CSS Custom Properties
 - Dark theme: navy/blue-black with cyan accents
 - Light theme: clean white with indigo accents
- HFT domain mock responses (latency, risk, market insights)
- Implement responsive layout (mobile, tablet, desktop)
- Add SDD documentation and development workflow guide


Resolves: initial project setup
SDD-REF: SDD-TEAM12-001 v2.0.0"
```


#### Push to remote:


```bash
git push origin main
```


> **Note:** If pushing to a new repository, set the remote first:
>
> ```bash
> git remote add origin <repository-url>
> git push -u origin main
> ```


---


## Quick Reference — Commands


| Action            | Command             |
| ----------------- | ------------------- |
| Install deps      | `npm install`       |
| Dev server        | `npm run dev`       |
| Production build  | `npm run build`     |
| Preview build     | `npm run preview`   |
| Lint              | `npm run lint`      |
| Stage all         | `git add .`         |
| Commit            | `git commit -m "…"` |
| Push              | `git push origin main` |


---

## Phase 3: OrgBot Slack Bot — Live Setup

> The OrgBot backend (`core/`, `services/api/`, `ingestion/`) is the RAG knowledge agent; the Slack bot (`services/slackbot/`) fronts it. Follow these steps to run the bot against a real workspace.

### 1. Create the Slack App

1. Go to <https://api.slack.com/apps> → **Create New App** → *From an app manifest* (or *From scratch* and fill the same fields manually).
2. Suggested manifest (exact name/icon are up to you):

   ```yaml
   display_information:
     name: OrgBot
     description: Org knowledge agent - Q&A with SME feedback
   features:
     bot_user:
       display_name: OrgBot
       always_online: true
   oauth_config:
     scopes:
       bot:
         - chat:write          # post threaded answers and buttons
         - app_mentions:read   # receive @OrgBot mentions
         - channels:history    # live Slack ingestion (public channels)
         - conversations:history
         - commands            # slash commands / interactivity
         - interactive         # buttons and modals
   settings:
     event_subscriptions:
       request_url: https://<your-host>/slack/events   # HTTP Events mode only
       bot_events:
         - app_mention
     interactivity:
       request_url: https://<your-host>/slack/events   # HTTP Events mode only
     socket_mode_enabled: true                         # Socket Mode for local dev
     socket_mode_install:
       app_level_token: xapp-...                       # generated after enabling
   ```

   > **Scope note:** the bot uses **Block Kit buttons** for feedback, so the plan's
   > original `reactions:read` scope is **not** required. Scopes needed are
   > `chat:write`, `app_mentions:read`, `channels:history`, `conversations:history`,
   > `commands`, and `interactive`.

3. **Install the app** to your workspace (*Install to Workspace*) and copy the **Bot User OAuth Token** (`xoxb-...`).
4. If using **Socket Mode**, enable it in *Socket Mode* and generate an **App-Level Token** (`xapp-...`).

### 2. Set Environment Variables

| Env var | Value |
|---------|-------|
| `SLACK_BOT_TOKEN` | Bot User OAuth Token (`xoxb-...`) |
| `SLACK_APP_TOKEN` | App-Level Token (`xapp-...`) — Socket Mode only |
| `SLACK_SIGNING_SECRET` | Signing Secret (Settings → Basic Information) — HTTP Events mode only |

Tokens are **only** read from these env vars and are never logged. Startup fails loudly if the token required by the configured mode is missing.

#### LLM provider: Anthropic vs local Ollama

By default the RAG pipeline calls the Anthropic API (needs `ANTHROPIC_API_KEY`). To run fully local with **Ollama** (no API key), set in `config/config.yaml`:

```yaml
llm:
  provider: ollama
  model: llama3.2:3b          # any model from `ollama list`
  base_url: http://localhost:11434
  api_key_env: ANTHROPIC_API_KEY   # unused when provider is ollama
```

The `AnswerGenerator` and `GraphRetriever` (LLM Cypher) both talk to Ollama's `/api/chat` via httpx; if Ollama is unreachable they fall back to offline evidence responses. Embeddings need no key either — with `provider: voyage3` and no `VOYAGE_API_KEY` set, the embedder falls back to deterministic local hashing at the configured dimension. Start Ollama (`ollama serve`) before running the bot.

### 3. Configure `config/config.yaml`

```yaml
slack:
  source: simulated        # set to "live" to ingest real channel history
  socket_mode: true        # true = Socket Mode; false = HTTP Events endpoint
  bot_token_env: SLACK_BOT_TOKEN
  app_token_env: SLACK_APP_TOKEN
  signing_secret_env: SLACK_SIGNING_SECRET
  channels: []             # allowlist for live ingestion, e.g. ["C01ABC123"]
  messages_fetch_limit: 100
```

- `source: simulated` (default) keeps offline behavior; live mode is only active when `source: live` **and** `SLACK_BOT_TOKEN` is set. The scheduler logs a warning and skips live Slack if the token is missing.
- Live ingestion tracks a per-channel cursor (`slack:<channel_id>` in PostgreSQL) and excludes the bot's own messages (`bot_id` / `subtype: bot_message`).

### 4. Run the Bot

```bash
# Socket Mode (recommended for local development)
python -m services.slackbot.app
# or, after `pip install -e .`
orgbot-slackbot

# HTTP Events mode
python -m services.slackbot.app --config path/to/config.yaml
```

The `@app_mention` event, the `feedback:*` block actions, and the
`feedback_correction` modal are all wired to the in-process pipeline and feedback
loop in `services/slackbot/app.py`.

### 5. Manual Smoke Test

1. Start the API prerequisites (ChromaDB, Neo4j, PostgreSQL) and ingest the simulated corpus:
   ```bash
   python -m simulators.generate_all
   python -m ingestion.ingest_all
   ```
2. Start the bot (Socket Mode) and invite it to a channel.
3. Mention the bot: `@OrgBot Who should I contact about a FIX session disconnect?`
   - Expect a threaded reply with a confidence badge (🟢 ≥ 0.7 / 🟡 0.4–0.7 / 🔴 < 0.4), the answer, and source citations.
4. Click **✅ Correct** → an approval is recorded (boosts future confidence).
5. Click **❌ Incorrect** or **📝 Needs correction** → a modal opens; submit the correct answer/context → recorded via the feedback loop (`sme_id` = your Slack user id).
6. Verify the bot never responds to or ingests its own messages.
7. Optional live ingestion: set `slack.source: live`, populate `slack.channels`, restart the scheduler, and watch per-channel cursors advance in PostgreSQL.

### 6. Demo & Benchmark

```bash
python scripts/demo_queries.py                 # representative queries: answer + confidence + sources
python scripts/benchmark_golden_pairs.py       # 20 golden pairs, confidence-vs-correctness correlation
```
