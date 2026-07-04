# ScriptSpark

ScriptSpark is an AI story-generation app with a React/Vite frontend and a FastAPI backend. It can generate scene-based stories, enrich prompts with local Telangana fact retrieval, export scripts, and optionally create ElevenLabs voiceovers.

## Project Structure

- `frontend/` - React, Vite, Tailwind, shadcn/ui
- `backend/` - FastAPI API, Gemini story generation, optional FAISS retrieval, optional ElevenLabs voiceover

## Local Setup

### Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.template .env
uvicorn app.main:app --reload
```

Add your real keys to `backend/.env`. Do not commit `.env`.

If `backend/requirements.txt` is still a OneDrive placeholder, use `backend/requirements-prod.txt`:

```powershell
pip install -r requirements-prod.txt
```

If your old environment shows a FAISS/NumPy error like `_ARRAY_API not found`, install with `numpy<2` or rebuild the environment from `backend/requirements-prod.txt`.

### Frontend

```powershell
cd frontend
npm install
Copy-Item .env.example .env
npm run dev
```

The frontend defaults to `http://localhost:8000/api`.

## Deployment Notes

- Deploy `backend/` to a Python host such as Render, Railway, Fly.io, or a VPS.
- Set `GOOGLE_API_KEY`, `ELEVENLABS_API_KEY`, and `ALLOWED_ORIGINS` in the backend host environment.
- Deploy `frontend/` to Vercel/Netlify and set `VITE_API_BASE_URL` to your backend URL plus `/api`.
- Keep `backend/data/telangana_facts/index.faiss` and `docs.json` available if you want retrieval. If they are missing or FAISS is unavailable, the API still starts and story generation continues without retrieval context.
