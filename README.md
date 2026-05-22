# GreenPack EPR Service
# 🌐 Live Demo

The GreenPack EPR Compliance Service is fully deployed and live in production.  
You can access and test the live application here:

👉 https://greenpack-erp-compliance-services-ai-1-pn8x.onrender.com/

The deployed version includes:
- FastAPI backend
- AI-powered RAG policy Q&A
- Reconciliation analysis
- SQLite storage
- Groq LLM integration
- Modern enterprise UI/UX
<img width="1000" height="1200" alt="image" src="https://github.com/user-attachments/assets/68f2cc02-fe67-48b0-80cf-94e48e4402a9" />


A production-quality FastAPI service for plastic packaging **Extended Producer Responsibility (EPR)** compliance workflows. The service supports:

- **Declaration submission** — validate and persist quarterly plastic quantity declarations.
- **Reconciliation summary** — cross-check declarations against ERP procurement data with a Llama-3.3-70b-generated narrative.
- **Policy Q&A** — a RAG pipeline over EPR policy documents powered by local embeddings and Llama-3.3-70b.

---

## 1. Setup Instructions

### Prerequisites

- Python 3.10+
- A [Groq API key](https://console.groq.com/keys)

### Install dependencies

```bash
cd greenpack-epr
pip install -r requirements.txt
```

> **Note:** `sentence-transformers` will download the `all-MiniLM-L6-v2` model (~80 MB) on first run. This is cached locally and subsequent starts are fast.

### Configure environment

Create a `.env` file in the `greenpack-epr/` directory:

```env
GROQ_API_KEY=your_key_here
```

The key is loaded via `python-dotenv` and is **never hardcoded** in source.

### Run the server

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

On startup you will see:

```
GreenPack EPR Service started. FAISS index built with N chunks.
```

### Interactive API docs

Once running, open: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 2. LLM — Groq API · llama-3.3-70b-versatile



**Why Groq + Llama 3.3 70B?**  
`llama-3.3-70b-versatile` running on Groq's LPU (Language Processing Unit) infrastructure was chosen because it is:
- **Ultra-fast** — Groq delivers token generation at 200-300+ tokens/second, far exceeding GPU-based APIs for interactive compliance tasks.
- **High quality** — Llama 3.3 70B rivals frontier models on structured generation, summarisation, and grounded Q&A tasks.
- **Cost-effective** — Groq's pricing is competitive; the free tier covers substantial development and demo workloads.
- **OpenAI-compatible interface** — The Groq Python SDK uses `client.chat.completions.create()`, making the integration clean and easy to reason about.
- **No vendor lock-in** — The open-weight Llama 3.3 model can be self-hosted if needed.

---

## 3. Embedding Model — all-MiniLM-L6-v2

`sentence-transformers/all-MiniLM-L6-v2` was chosen because it is:
- **Free and local** — runs on CPU, no API calls, zero per-query cost.
- **Fast** — 14,000 sentences/second on modern hardware.
- **High quality** — achieves competitive scores on the BEIR retrieval benchmark for its size class.
- The model produces **384-dimensional** embeddings normalised before FAISS indexing for cosine-similarity semantics.

---

## 4. Storage — SQLite

SQLite was chosen because:
- **Zero configuration** — no server to provision; the database is a single file (`greenpack.db`).
- **Built-in** — uses Python's `sqlite3` standard library; no additional driver needed.
- **Sufficient for this workload** — compliance declaration workflows are low-write, low-concurrency. SQLite handles thousands of writes/second, well beyond EPR reporting volumes.

---

## 5. Vector Store — FAISS

`faiss-cpu` was chosen because:
- **Lightweight** — no server, no infrastructure; the index lives in memory.
- **Fast** — exact nearest-neighbor search over hundreds of chunks completes in microseconds.
- **Sufficient** — the EPR corpus is small (~4 documents, ~20 chunks); Pinecone or Qdrant would be overkill.

---

## 6. AI Coding Assistant

This project was built using **Antigravity** (an AI-native coding environment) powered by the **claude.ai** model, used for:
- Generating the full project scaffold including all module boilerplate.
- Drafting realistic mock EPR policy documents for the RAG corpus.
- Writing and iterating on Pydantic validation logic for edge cases.
- Producing the `demo.sh` curl script.

---

## 7. RAG Corpus Sources




All four documents in `data/epr_corpus/` are **fabricated mock policy documents** created for demonstration purposes. They are based on publicly available knowledge of the Indian EPR and CPCB regulatory framework:

| File | Topic |
|------|-------|
| `doc1_epr_rules.txt` | EPR Rules — who must register, phased targets, deadlines |
| `doc2_plastic_categories.txt` | Plastic categories — rigid, flexible, multilayer, compostable definitions |
| `doc3_cpcb_guidelines.txt` | CPCB portal registration, quarterly reporting, penalties |
| `doc4_producer_obligations.txt` | Collection targets, buy-back pricing, EPR certificate rules |

**Disclaimer:** These documents are fictional and should not be used for actual legal or compliance guidance. Consult official CPCB publications for authoritative information.

---

## 8. One Thing I'd Do Differently With Another Day

**Persist the FAISS index to disk.**

Currently, `rag.build_index()` runs on every server startup, re-embedding all corpus chunks each time. With a larger corpus (hundreds of documents), startup time would become unacceptable.

The fix: serialize the FAISS index with `faiss.write_index(index, "faiss.index")` and the metadata list with `pickle` or `json`, then load them on startup if the files exist and the corpus hasn't changed (checked via a hash of the corpus directory). This would reduce cold-start time from seconds to milliseconds.

Additional improvements I'd make:
- Add a `POST /corpus/reload` admin endpoint to hot-reload the FAISS index without restarting.
- Switch from SQLite to PostgreSQL for multi-process deployments.
- Add structured logging (JSON) for production observability.
- Add authentication (API key header) to all endpoints.

---

## 9. Deploy on Render

### Prerequisites
- A [Render account](https://render.com) (free tier is sufficient)
- This repository pushed to a GitHub or GitLab repo

### Step-by-step

1. **Push to GitHub**
   ```bash
   git init && git add . && git commit -m "Initial commit"
   git remote add origin https://github.com/YOUR_USERNAME/greenpack-epr.git
   git push -u origin main
   ```

2. **Create a new Web Service on Render**
   - Go to [render.com](https://render.com) → **New → Web Service**
   - Connect your GitHub repository
   - Select the `greenpack-epr/` directory as the root (or the repo root if that's where the code lives)

3. **Configure the service**

   | Setting | Value |
   |---------|-------|
   | **Runtime** | Python 3 |
   | **Build Command** | `pip install -r requirements.txt` |
   | **Start Command** | `uvicorn main:app --host 0.0.0.0 --port $PORT` |

4. **Set environment variables** _(Render Dashboard → Environment → Environment Variables)_

   | Key | Value |
   |-----|-------|
   | `GROQ_API_KEY` | Your Groq API key from [console.groq.com/keys](https://console.groq.com/keys) |

   > ⚠️ **Never commit your `.env` file to version control.** Only set the key through the Render dashboard.

5. **Deploy** — Click **Deploy Web Service**. Render will:
   - Install dependencies (`pip install -r requirements.txt`)
   - Start the server (`uvicorn main:app --host 0.0.0.0 --port $PORT`)
   - Run startup checks (env validation → SQLite init → FAISS index build)
   - Serve the frontend at `https://your-service.onrender.com/`

### What you get on Render

| URL | Description |
|-----|-------------|
| `https://your-service.onrender.com/` | HTML dashboard (frontend.html) |
| `https://your-service.onrender.com/health` | Uptime/liveness probe |
| `https://your-service.onrender.com/docs` | Interactive API docs (Swagger) |
| `https://your-service.onrender.com/submit` | POST — declaration submission |
| `https://your-service.onrender.com/summary/{id}/{month}` | GET — reconciliation |
| `https://your-service.onrender.com/ask` | POST — RAG Q&A |

### Notes
- **SQLite persistence:** Render's free tier uses an ephemeral filesystem — the `greenpack.db` file resets on each redeploy/restart. For persistent data, upgrade to a paid plan with a Render Disk, or migrate to PostgreSQL.
- **Cold starts:** The free tier spins down after 15 minutes of inactivity. The first request after a cold start takes ~15-20 seconds (sentence-transformer model load). This is normal.
- **FAISS index:** Re-built in memory on every startup from the corpus `.txt` files, which are part of the repo. No additional configuration needed.



### `POST /submit`

Submit a plastic packaging declaration.

```json
{
  "producer_id": "GREENPACK-001",
  "month": "2026-04",
  "declared_quantities_kg": {
    "rigid_plastic": 12000,
    "flexible_plastic": 8500,
    "multilayer_plastic": 3200
  }
}
```

### `GET /summary/{producer_id}/{month}`
<img width="800" height="1000" alt="image" src="https://github.com/user-attachments/assets/a14e539f-e9b6-4bb8-ba0d-8c77423ce49f" />

Get reconciliation summary vs. ERP feed with LLM narrative.

```
GET /summary/GREENPACK-001/2026-04
```

### `POST /ask`

Ask a compliance question using RAG over the EPR policy corpus.
<img width="900" height="1000" alt="image" src="https://github.com/user-attachments/assets/9badda40-4941-4788-9936-ff8f2273501a" />

```json
{
  "question": "What are the EPR registration requirements?"
}
```

---

## Project Structure

```
greenpack-epr/
├── main.py              # FastAPI app, all 3 endpoints, lifespan
├── models.py            # Pydantic v2 models
├── storage.py           # SQLite helpers (init, insert, fetch)
├── reconcile.py         # Deterministic reconciliation logic
├── rag.py               # RAG pipeline (embeddings + FAISS)
├── llm.py               # Groq API wrappers
├── data/
│   ├── erp_feed.csv     # Mock ERP procurement data
│   └── epr_corpus/      # 4 mock EPR policy documents
├── greenpack.db         # SQLite database (auto-created)
├── requirements.txt
├── README.md
└── demo.sh              # curl demo script
```
