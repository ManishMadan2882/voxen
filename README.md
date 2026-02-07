# Telephony Agent Prototype (Minimal)

A minimal, resume-friendly voice-agent backend that simulates a telephony call flow over HTTP.
It supports intent detection, order status, return policy, account verification, and live-agent handoff.

## Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 3000
```

Server starts on `http://localhost:3000`.

## LLM Layer (Hot Swap)

The LLM layer is optional and falls back to deterministic rules if disabled or if the LLM fails.

Enable it via env vars:

```bash
export LLM_ENABLED=true
export LLM_PROVIDER=ollama     # or gemini
export LLM_MODEL=gemma3        # for Ollama
export OLLAMA_URL=http://localhost:11434/api/generate

# For Gemini:
# export LLM_PROVIDER=gemini
# export LLM_MODEL=gemini-1.5-flash
# export GEMINI_API_KEY=your_key
```

## Example Call Flow

Start a call session:

```bash
curl -s -X POST http://localhost:3000/call/start | jq
```

Use the returned `sessionId` for turns.

Order status flow:

```bash
curl -s -X POST http://localhost:3000/call/turn \
  -H 'Content-Type: application/json' \
  -d '{"sessionId":"<SESSION>","text":"I want my order status"}' | jq

curl -s -X POST http://localhost:3000/call/turn \
  -H 'Content-Type: application/json' \
  -d '{"sessionId":"<SESSION>","text":"Order A1234","orderId":"A1234"}' | jq
```

Return policy flow:

```bash
curl -s -X POST http://localhost:3000/call/turn \
  -H 'Content-Type: application/json' \
  -d '{"sessionId":"<SESSION>","text":"What is your return policy?"}' | jq
```

Account verification flow:

```bash
curl -s -X POST http://localhost:3000/call/turn \
  -H 'Content-Type: application/json' \
  -d '{"sessionId":"<SESSION>","text":"I need account verification"}' | jq

curl -s -X POST http://localhost:3000/call/turn \
  -H 'Content-Type: application/json' \
  -d '{"sessionId":"<SESSION>","text":"My last 4 are 1234","last4":"1234"}' | jq
```

Live-agent handoff:

```bash
curl -s -X POST http://localhost:3000/call/turn \
  -H 'Content-Type: application/json' \
  -d '{"sessionId":"<SESSION>","text":"I want a human agent"}' | jq
```

Streaming (SSE):

```bash
curl -N -s -X POST http://localhost:3000/call/stream \
  -H 'Content-Type: application/json' \
  -d '{"sessionId":"<SESSION>","text":"I want my order status","orderId":"A1234"}'
```

## Notes

- This is an HTTP simulation of a telephony agent.
- You can later replace the HTTP layer with Twilio, Exotel, Plivo, or SIP events.
- Add ASR/TTS integration by wiring speech-to-text and text-to-speech services into `/call/turn`.
