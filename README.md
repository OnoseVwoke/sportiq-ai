# SportIQ AI — starter scaffold

AI-powered football predictions website/app. This is the DevOps-style
scaffold: Dockerized services wired together with Docker Compose,
matching the same pattern used for the Dream Vacation App project.

## What's built so far

| Service | Status | What it does |
|---|---|---|
| `db` | ✅ Ready | Postgres, schema in `db/init.sql` (teams, fixtures, predictions, users) |
| `backend` | ✅ Ready | FastAPI service — `/fixtures` and `/predictions/{id}` endpoints |
| `data-pipeline` | ✅ Ready (placeholder data) | Fetches fixtures, saves to DB, generates predictions. Currently uses fake sample data — real API + real model come later |
| `frontend` | ⏭️ Not built yet | Coming in the next step |

## Folder structure

```
sportiq-ai/
├── docker-compose.yml   # wires all 4 services together
├── .env.example         # copy to .env and fill in real values
├── db/
│   └── init.sql         # database schema
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/main.py
├── data-pipeline/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── pipeline.py
└── frontend/             # empty for now
```

## How to run it (once Docker is installed — see setup guide)

1. Copy `.env.example` to `.env` and fill in a password (API keys can wait)
2. From this folder, run: `docker compose up --build`
3. Backend health check: http://localhost:5000/health
4. Backend fixtures (will be empty until the pipeline runs): http://localhost:5000/fixtures
5. Run the pipeline once to populate sample data: `docker compose run --rm data-pipeline`
6. Re-check http://localhost:5000/fixtures — you should now see 2 sample fixtures
