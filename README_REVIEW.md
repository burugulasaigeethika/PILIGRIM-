# PilgrimAI — Temple Pilgrimage & Travel Assistant (Frontend Review)

Welcome to the PilgrimAI repository review package. This project is a full-stack, offline-first artificial intelligence platform and interactive temple pilgrimage guide designed for the sacred shrines of Telangana and Andhra Pradesh.

---

## 1. What the Project Contains

- **React Frontend (`/frontend`)**:
  - Built with **React 18 + Vite + Lucide React**.
  - Modern dashboard with cream `#F8F5EE` background, forest green `#123C32` hero banner, and saffron `#D96B24` accents.
  - Interactive **Ask PilgrimAI** chat card and full-page **Travel Assistant** modal with multi-turn conversation memory, speech synthesis (listen aloud), and browser voice input.
  - Interactive **Trip Planner** supporting 20 certified temples, dynamic route sequence, day/pax/budget controls, accommodation/transport/food tiers, and save options.
  - **My Saved Itineraries** modal displaying personalized saved pilgrimage plans.
  - **Canonical Temples Directory** browsing all 20 certified shrines with state filtering.
  - **Auth System** for user login, registration, and profile sync.
- **Backend (`/backend`)**:
  - **FastAPI** server providing REST APIs for chat, maps/temples, itinerary planning, authentication, and chat history.
  - **Master Agent Coordinator** and 10 specialist agents (`temple_information`, `itinerary_planning`, `comparison`, `budget`, `live_navigation`, `live_weather`, etc.).
  - **Hybrid Offline RAG Pipeline**: Local on-disk Qdrant vector database (4,611 chunks) + BM25 index (4,458 docs) combined via Reciprocal Rank Fusion (RRF) and reranked using Cross-Encoder.
  - **Local LLM**: Ollama running quantized `qwen2.5:1.5b`.
- **Precompiled Production Web Assets (`/backend/app/static`)**:
  - The compiled production React bundle is directly hosted by FastAPI at `http://127.0.0.1:8000/`.
  - Non-destructive backup of original assets preserved in `/backend/app/static_backup/`.

---

## 2. Frontend Installation & Local Dev

### Requirements
- **Node.js**: v18+ (tested on Node v22.18.0)
- **npm**: v9+

### Steps
```bash
# 1. Navigate to the frontend directory
cd frontend

# 2. Install dependencies
npm install

# 3. Start the Vite development server (runs with API proxy to port 8000)
npm run dev
```
The Vite dev server will run on `http://localhost:5173/`.

### Building for Production
```bash
cd frontend
npm run build
```
This builds and outputs the static assets directly into `backend/app/static/`.

---

## 3. Backend Configuration & Environment Variables

Copy `.env.example` to `.env` in the root directory:
```bash
cp .env.example .env
```

### Key Environment Variables
- `OLLAMA_BASE_URL`: `http://localhost:11434` (Ollama local inference server).
- `LLM_MODEL`: `qwen2.5:1.5b`
- `QDRANT_DIR`: `./qdrant_db` (Local on-disk vector database directory).
- `BM25_DIR`: `./bm25_index` (Local keyword search index directory).
- `MONGODB_URL`: `mongodb://localhost:27017` (Used for user accounts and chat history storage).
- `MONGODB_DATABASE`: `pilgrim_ai`
- `JWT_SECRET_KEY`: A secure random string for JWT session authentication.
- `GOOGLE_MAPS_API_KEY`: *(Optional)* For Google Maps embed and Google Places live search. The application runs 100% offline if omitted.
- `GOOGLE_ROUTES_API_KEY`: *(Optional)* For live driving routes.

---

## 4. How to Start the Backend Server

### Requirements
- **Python**: 3.11 or 3.13
- **Ollama**: Installed and running locally (`ollama serve`, with `qwen2.5:1.5b` pulled)
- **MongoDB**: Running locally on port 27017

```bash
# Install backend Python dependencies
pip install -r requirements.txt

# Start the FastAPI server
python run_server.py
```
The server will be live at:
- **Web Application**: `http://127.0.0.1:8000/`
- **Interactive OpenAPI Docs**: `http://127.0.0.1:8000/docs`
- **Health Check**: `http://127.0.0.1:8000/health`

---

## 5. Backend APIs Expected by the Frontend

| Endpoint | Method | Purpose |
| :--- | :--- | :--- |
| `/chat` | `POST` | Multi-agent offline RAG queries. Request: `{ question, session_id }`. Returns `{ answer, agent_name, confidence_score, latency_ms, sources, retrieved_chunks, metadata }`. |
| `/api/maps/temples` | `GET` | Returns list of 20 canonical verified shrines with geo-coordinates, district, and state. |
| `/api/maps/config` | `GET` | Returns runtime enablement state and safe browser key for maps. |
| `/api/itinerary/plan` | `POST` | Generates verified day-by-day pilgrimage itinerary and budget breakdown. |
| `/api/itinerary/save` | `POST` | Saves an itinerary to the authenticated user's profile. |
| `/api/itinerary/saved` | `GET` | Retrieves all saved itineraries for the authenticated user. |
| `/api/itinerary/saved/{id}`| `DELETE` | Deletes a saved itinerary from user profile. |
| `/api/chat/history` | `GET` | Lists previous chat conversation sessions for the authenticated user. |
| `/api/chat/history/{id}` | `GET` | Retrieves all messages for a specific chat conversation. |
| `/api/auth/register` | `POST` | User registration (`name`, `email`, `password`). |
| `/api/auth/login` | `POST` | User login (`email`, `password`) -> JWT `access_token`. |
| `/api/auth/me` | `GET` | Returns currently authenticated user details. |

---

## 6. External Services & Optional Keys

- **Ollama (`qwen2.5:1.5b`)**: **Required for local AI generation**. Ensure Ollama is running (`ollama serve`).
- **Google Maps / Places / Routes API**: **Optional**. If keys are not configured, the system uses the verified offline temple coordinate knowledge base and offline routing baselines.
- **SMTP Server**: **Optional**. Only required for sending password reset emails (`/api/auth/forgot-password`).

---

## 7. Known Notes & Observations

- The RAG system operates 100% offline using local embeddings (`all-MiniLM-L6-v2`) and cross-encoder rerankers without transmitting data to external cloud LLMs.
- Chat history and saved itineraries require being signed in via the user profile menu to maintain strict user data isolation.
- On browsers that do not support the Web Speech API, the voice input button gracefully alerts the user while keyboard input remains fully functional.
