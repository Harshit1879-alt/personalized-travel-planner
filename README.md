# Personalized Travel Itinerary Planner

A runnable full-stack starter for an AI-powered travel planner.

## Features
- React + Vite responsive SaaS dashboard
- Trip preferences: destination, dates, days, budget, travel style, party, interests
- AI itinerary generation using Gemini or Groq (optional); deterministic demo mode works without API keys
- Itinerary day cards, estimated costs, activity swap, regenerate trip
- FastAPI backend with SQLite trip history
- Export a trip to a printable PDF
- Optional Supabase persistence configuration

## Requirements
- Node.js 18+
- Python 3.10+

## 1. Start the backend
```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload
```
Backend runs at http://127.0.0.1:8000. API docs: http://127.0.0.1:8000/docs

On macOS/Linux, use `cp .env.example .env` instead of `copy`.

## 2. Start the frontend
Open a second terminal:
```bash
cd frontend
npm install
npm run dev
```
Open the URL printed by Vite (usually http://localhost:5173).

## 3. Optional AI setup
In `backend/.env`, set **one** provider:
```env
AI_PROVIDER=gemini
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-2.5-flash
```
or
```env
AI_PROVIDER=groq
GROQ_API_KEY=your_key_here
GROQ_MODEL=llama-3.3-70b-versatile
```
Never put API keys in the React frontend. Without a key, the app uses demo itinerary generation.

## 4. Optional Supabase
Create a Supabase project and run `backend/supabase_schema.sql` in the SQL Editor. Add:
```env
SUPABASE_URL=https://YOUR_PROJECT.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key
```
The app currently uses SQLite by default for simple local setup. Supabase variables/schema are included as the integration starting point; wire your project-specific table operations before deploying publicly. Keep service-role keys on the backend only.

## Project structure
```text
backend/
  app/main.py
  requirements.txt
  .env.example
  supabase_schema.sql
frontend/
  src/App.jsx
  src/main.jsx
  src/styles.css
  index.html
  package.json
```

## Notes before production
This is a starter project, not a production deployment. Add authentication, authorization, rate limits, request validation, provider error handling/observability, secure secrets, and real maps/weather/places data before public launch. AI-generated costs and opening hours are estimates and must be verified.
