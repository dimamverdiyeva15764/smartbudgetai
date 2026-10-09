# SmartBudget AI

React/Vite frontend (`frontend/`) + Django REST backend (`backend/`), deployed as two
Vercel services (`vercel.json`): `/api/*` → Django, everything else → the Vite build.

Flow: registration → 10-step questionnaire (each step saved on the server) →
`POST /api/financial-inquiry/complete/` → processing screen (polls
`/api/financial-inquiry/status/`) → 12-month dashboard → edit answers / recalculate →
Excel / PDF export.

The 12-month plan is calculated in `backend/users/budget_engine.py` following
*SmartBudget_AI_Final_System_Prompt* (12 separate months, seasonal variation,
Income = all categories + savings + balance, annual totals = sum of months).
If `GROQ_API_KEY` is set, the LLM only rewrites the explanation texts; numbers are
never taken from the LLM.

## Environment variables

| Where | Name | Secret | Notes |
|---|---|---|---|
| backend | `DATABASE_URL` | yes | **Required in production.** Postgres URL (Neon / Vercel Postgres / Supabase). Without it Vercel uses a temporary SQLite in `/tmp` that loses users. `POSTGRES_URL` is also accepted. |
| backend | `DJANGO_SECRET_KEY` | yes | Long random string. |
| backend | `GROQ_API_KEY` | yes | Optional. Friendlier AI texts. |
| backend | `DEBUG` | no | `False` in production (default on Vercel). |
| backend | `AUTO_MIGRATE` | no | Default `true` on Vercel: runs `migrate` on cold start. |
| backend | `GROQ_MODEL`, `AI_TIMEOUT_SECONDS` | no | Optional. |
| frontend | `VITE_API_BASE_URL` | no | Leave unset on Vercel (`/api`). Local default `http://127.0.0.1:8000/api`. |

## Local development

```bash
# backend
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py test users
python manage.py runserver 127.0.0.1:8000

# frontend (second terminal)
cd frontend
npm install
npm run dev        # http://localhost:5173
```
