# 🤖 CallingBot — AI Outbound Voice Agent

An AI-powered outbound calling agent built with **LiveKit**, using **fully local/open-source AI** — no paid API keys needed for AI services.

| Component | Technology | Runs On |
|-----------|-----------|---------|
| **Voice Agent** | LiveKit Agents SDK | Python |
| **Speech-to-Text** | Whisper (faster-whisper) | Docker (CPU) |
| **Text-to-Speech** | Kokoro FastAPI | Docker (CPU) |
| **LLM** | Ollama (Llama 3.2 1B) | Local |
| **Telephony** | LiveKit SIP + Vobiz | Cloud |

## 🚀 Features
- **Fully Local AI** — Whisper STT, Kokoro TTS, Ollama LLM — no cloud AI costs
- **Smart Intent Detection** — Keyword matching + LLM fallback for ambiguous responses
- **Outbound SIP Calls** — Automated calling via Vobiz SIP trunk
- **Lead Capture** — Saves interested leads to `lead.csv`
- **Windows Compatible** — Tested on Windows with ProactorEventLoop fix

---

## � Prerequisites

- **Python 3.10+**
- **Docker Desktop** — [Download](https://www.docker.com/products/docker-desktop/)
- **Ollama** — [Download](https://ollama.ai/download)
- **LiveKit Cloud Account** — [Sign up](https://cloud.livekit.io/) (free tier available)
- **SIP Provider** — e.g., [Vobiz](https://vobiz.ai/) for phone calls

---

## 🛠️ Setup (Step-by-Step)

### Step 1: Clone the Repository
```bash
git clone https://github.com/your-username/CallingBot.git
cd CallingBot
```

### Step 2: Install Ollama + Pull LLM Model
```bash
# After installing Ollama from https://ollama.ai/download
ollama pull llama3.2:1b
```
Verify it's running:
```bash
ollama list
# Should show: llama3.2:1b
```

### Step 3: Start Whisper & Kokoro (Docker)
```bash
docker compose -f docker-compose-ai.yml up -d
```
This starts:
- **Whisper STT** on `http://localhost:8000`
- **Kokoro TTS** on `http://localhost:8880`

Verify both are running:
```bash
docker ps
# Should show two containers: whisper and kokoro
```

> **Note:** First startup may take a few minutes as Docker downloads the images (~2-3 GB).

### Step 4: Create Python Virtual Environment
```bash
python -m venv venv

# Activate it:
# Windows (PowerShell):
.\venv\Scripts\activate

# Linux/Mac:
source venv/bin/activate
```

### Step 5: Install Python Dependencies
```bash
pip install -r requirements.txt
```

### Step 6: Configure Environment Variables
```bash
# Windows:
copy .env.example .env

# Linux/Mac:
cp .env.example .env
```
Edit `.env` and fill in your credentials:

```env
# LiveKit (required) — get from https://cloud.livekit.io/
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your_api_key
LIVEKIT_API_SECRET=your_api_secret

# SIP Trunk (required for calls) — get from your SIP provider
VOBIZ_SIP_TRUNK_ID=your_trunk_id
VOBIZ_SIP_DOMAIN=your_sip_domain
VOBIZ_USERNAME=your_username
VOBIZ_PASSWORD=your_password
VOBIZ_OUTBOUND_NUMBER=your_outbound_number
```

> The AI service URLs (`WHISPER_BASE_URL`, `KOKORO_BASE_URL`, `OLLAMA_BASE_URL`) have sensible defaults and usually don't need changing.

---

## 🏃 Running

### Terminal 1: Start the Agent
```bash
python agent.py start
```
Wait until you see:
```
registered worker ... agent_name: "outbound-agent"
```

### Terminal 2: Make a Call
```bash
python make_call.py --to +91XXXXXXXXXX
```
> Replace with the actual phone number (must include country code).

---

## � Call Flow

1. Agent dials the phone number via SIP
2. On answer, plays greeting: *"Hello, I am calling from Kickr Technology..."*
3. Listens for response using VAD (Voice Activity Detection)
4. Transcribes speech with Whisper
5. Classifies intent (keywords first, LLM for ambiguous)
6. If **interested** → saves lead to `lead.csv`, says thank you, hangs up
7. If **not interested** → says goodbye, hangs up
8. If **unclear** → asks again (max 3 attempts)

---

## 📂 Project Structure

| File | Description |
|------|-------------|
| `agent.py` | Main voice agent — VAD, STT, TTS, intent classification |
| `config.py` | All configuration — prompts, URLs, messages |
| `make_call.py` | Script to dispatch outbound calls |
| `lead.csv` | Auto-generated lead storage |
| `.env` | Your credentials (never commit this!) |
| `docker-compose-ai.yml` | Whisper + Kokoro Docker services |
| `docker-compose.yml` | Agent Docker deployment (optional) |
| `Dockerfile` | Container build for the agent |
| `requirements.txt` | Python dependencies |

---

## � Troubleshooting

### Services not responding
```bash
# Check Docker containers
docker ps

# Check Ollama
ollama list

# Test endpoints manually (PowerShell):
Invoke-WebRequest -Uri "http://localhost:8000/v1/models" -UseBasicParsing
Invoke-WebRequest -Uri "http://localhost:8880/v1/models" -UseBasicParsing
Invoke-WebRequest -Uri "http://localhost:11434/v1/models" -UseBasicParsing
```

### Port 8081 already in use
Another agent instance is running. Kill it:
```bash
# Windows:
taskkill /F /IM python.exe

# Linux:
pkill -f "python agent.py"
```

### Call connects but no audio
- Check Kokoro TTS is running: `docker logs <kokoro-container-name>`
- Verify the TTS URL in `.env` matches the running service

### SIP Trunk errors
- Verify `VOBIZ_SIP_TRUNK_ID` in `.env` matches your LiveKit project
- Check SIP credentials are correct

---

## 🐳 Docker Deployment (Optional)

To run the agent itself in Docker:
```bash
docker compose up -d
```
> Make sure `.env` is configured and Whisper/Kokoro/Ollama are accessible from the container.

---

## 📄 License
MIT
