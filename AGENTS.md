# AGENTS.md

## Project Overview

Sistem Arsip Digital — Indonesian digital archive management system for a prosecutor's office (Kejaksaan). Manages physical archive locations (lemari/rak), legal cases (perkara), files (berkas), borrowing, and audit logging with AI-powered anomaly detection.

## Architecture

Three independent services, no monorepo tooling:

| Service | Stack | Port | Entry |
|---------|-------|------|-------|
| Backend | Node.js / Express 5 (CommonJS) | 3000 | `backend/server.js` → `backend/app.js` |
| Frontend | React 19 / Vite 8 (ESM) | 5173 | `frontend/src/main.jsx` |
| AI Service | Python / FastAPI / PyTorch VAE | 8000 | `ai-service/app.py` |

- **Database**: PostgreSQL. Schema reference: `database/schema.sql`. Manual migrations in `database/migrations/` — not automated.
- **Frontend also has Electron** support: `frontend/electron/main.js` (run with `npm run electron`).
- Backend auto-applies some schema alterations on startup (`app.js:18-70`), which means running the server can modify the DB.
- `ai-service/requirements.txt` still lists `tensorflow` but the runtime model is PyTorch (`services/inference.py` imports `torch`).

## Running the Services

### Backend
```bash
cd backend
# Create .env with DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD, JWT_SECRET, PORT
npm install
node server.js        # or: npm run dev (both run server.js)
```
- Requires PostgreSQL running with `sistem_arsip_digital` database.
- `.env` is gitignored but present at `backend/.env` — never commit real credentials.
- `nodemon` is a devDependency but the `dev` script still runs `node server.js` directly.

### Frontend
```bash
cd frontend
npm install
npm run dev           # Vite dev server on :5173
npm run build         # Production build
npm run lint          # ESLint
npm run electron      # Desktop app via Electron
```
- API URL defaults to `http://localhost:3000`, override with `VITE_API_URL` env var.

### AI Service
```bash
cd ai-service
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
# Create .env with HOST, PORT, DATABASE, USER, PASSWORD for PostgreSQL
uvicorn app:app --host 0.0.0.0 --port 8000
```
- Training: `python train.py`, preprocessing: `python preprocessing.py`
- Reads from `audit_log` table, scores via VAE reconstruction error.
- Model artifacts live in `ai-service/models/` (active) and `ai-service/model/` (legacy).
- `ai-service/stage7/` contains experimental forensic audit scripts — not part of the production pipeline.

## Code Conventions

### Backend (Node.js)
- CommonJS (`require`/`module.exports`). Express 5.
- Routes in `backend/routes/`, controllers in `backend/controllers/`, services in `backend/services/`.
- Middleware: `authMiddleware.js` (JWT), `roleMiddleware.js` (RBAC).
- JWT auth via `jsonwebtoken`. TOTP 2FA via `speakeasy`.
- All mutating operations write to `audit_log` via `auditLogService`.
- Email validation/normalization in `utils/accountSecurity.js`.

### Frontend (React)
- Functional components, React Router v7 for routing.
- Role-based access: `admin`, `arsiparis`, `user` — enforced in `AppRoutes.jsx` via `RequireRole`.
- Auth state stored in `localStorage` (`token`, `role`, `pendingAuthToken`).
- API layer: `src/services/apiService.js` (axios with auth interceptor).
- ESLint with `react-hooks` and `react-refresh` plugins (flat config).

### AI Service (Python)
- FastAPI with Pydantic schemas in `schemas/`.
- Inference logic in `services/inference.py`, model loading in `services/model_loader.py`.
- Config from `ai-service/config.py` (reads `.env` with fallback defaults).
- Input shape to VAE is `(n, 9)` — enforced in `services/inference.py:26`.

## Known Issues

- `TODO.md`: bcrypt redeclaration bug in `backend/controllers/userController.js` — check for duplicate `require("bcrypt")`.
- Backend `app.js` runs `ALTER TABLE` on every startup to ensure columns exist — this is intentional but unusual.
- `requirements.txt` lists `tensorflow` but inference actually uses PyTorch — the dependency list is stale.

## Database Notes

- Reference schema: `database/schema.sql` — this is documentation, not a migration runner.
- Migrations in `database/migrations/` must be applied manually.
- Roles: `admin`, `arsiparis`, `user` — seeded in `roles` table.
- Audit log chaining: each entry has `hash_sebelumnya` and `hash_entri` for integrity.
