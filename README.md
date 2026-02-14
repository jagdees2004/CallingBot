# 🤖 CallingBot — AI Outbound Voice Agent

A production-ready voice agent capable of making outbound calls using **LiveKit**, **Deepgram**, and **Groq (Llama 3.3)**.
Designed for reliability, speed, and ease of deployment.

| Component | Technology | Provider |
|-----------|-----------|----------|
| **Voice Agent** | LiveKit Agents SDK | Python |
| **Speech-to-Text** | Nova-2 | Deepgram |
| **Text-to-Speech** | Aura Asteria | Deepgram |
| **LLM** | Llama 3.3 70B | Groq |
| **Telephony** | SIP Trunking | Vobiz |

## 🚀 Features
- **Ultra-Fast LLM** — Groq running `llama-3.3-70b-versatile` for near-instant responses
- **High-Quality Audio** — Deepgram Nova-2 for STT, Aura Asteria for TTS
- **SIP Trunking** — Integrated with Vobiz for PSTN outbound calls
- **Lead Capture** — Auto-saves interested leads to `leads.csv`
- **Tool-Based Design** — LLM calls `save_lead` or `end_call` tools for deterministic behavior
- **Windows Compatible** — ProactorEventLoop fix included

---

## 🛠️ Setup & Installation

### 1. Prerequisites
- **Python 3.10+**
- A [LiveKit Cloud](https://cloud.livekit.io/) account
- A [Deepgram](https://deepgram.com/) API Key (free tier available)
- A [Groq](https://console.groq.com/) API Key (free tier available)
- A SIP Provider (e.g., [Vobiz](https://vobiz.ai/))

### 2. Clone & Install
```bash
git clone https://github.com/jagdees2004/CallingBot.git
cd CallingBot

# Create virtual environment
python -m venv venv

# Activate it
# Windows (PowerShell):
.\venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Environment
```bash
# Windows:
copy .env.example .env

# Linux/Mac:
cp .env.example .env
```

Edit `.env` and fill in your API keys:

```env
# Required
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your_api_key
LIVEKIT_API_SECRET=your_api_secret
DEEPGRAM_API_KEY=your_deepgram_key
GROQ_API_KEY=your_groq_key
VOBIZ_SIP_TRUNK_ID=your_trunk_id
```

---

## 🏃 Usage

### Terminal 1: Start the Agent
```bash
python agent.py start
```
Wait until you see:
```
registered worker ... agent_name: "outbound-agent"
```

### Terminal 2: Make an Outbound Call
```bash
python make_call.py --to +91XXXXXXXXXX
```
> Replace with the actual phone number (must include country code, e.g. +91, +1).

---

## 📞 Call Flow

```
1. Agent dials phone number via SIP
2. On answer → plays greeting
3. Listens for response (Deepgram STT + Silero VAD)
4. LLM classifies intent using tools:
   - User interested → calls save_lead() → saves to leads.csv
   - User not interested → calls end_call()
5. Speaks goodbye message
6. Hangs up and cleans up room
```

---

## 📂 Project Structure

| File | Description |
|------|-------------|
| `agent.py` | Main voice agent — VAD, STT, TTS, LLM, tool-based intent |
| `config.py` | All configuration — prompts, models, messages |
| `make_call.py` | Script to dispatch outbound calls |
| `leads.csv` | Auto-generated lead storage |
| `.env` | Your credentials (never commit!) |
| `docker-compose.yml` | Agent Docker deployment |
| `docker-compose-ai.yml` | Local AI services (Whisper + Kokoro) |
| `Dockerfile` | Container build for the agent |
| `requirements.txt` | Python dependencies |
| `create_trunk.py` | SIP trunk creation utility |
| `list_trunks.py` | List existing SIP trunks |

---

## 🔧 Troubleshooting

### Call connects but no audio from agent
1. Check Deepgram API key is valid and has credits
2. Check agent terminal logs for `APIStatusError`
3. Ensure the TTS model exists: `aura-asteria-en`

### `model_decommissioned` error (Groq)
Update `GROQ_MODEL` in `config.py` or `.env` to a supported model:
- `llama-3.3-70b-versatile` (default)
- `llama-3.1-8b-instant` (faster, less accurate)

### `Address already in use` (Port 8081)
```powershell
# Windows:
taskkill /F /IM python.exe

# Linux:
pkill -f "python agent.py"
```

### Missing modules
```bash
pip install -r requirements.txt
```

---

## 🐳 Docker Deployment

### Run the Agent in Docker
```bash
docker compose up -d
```

### Optional: Local AI Services (Whisper + Kokoro)
For offline/local development without Deepgram:
```bash
docker compose -f docker-compose-ai.yml up -d
```

---

## 📄 License
MIT
