# AGENTS.md

## Project Overview

Sistem Arsip Digital — Indonesian digital archive management system for a prosecutor's office (Kejaksaan). Manages physical archive locations (lemari/rak), legal cases (perkara), files (berkas), borrowing (peminjaman), integrity verification, and audit logging with AI-powered anomaly detection.

## Architecture

Three independent services, no monorepo tooling:

| Service | Stack | Port | Entry |
|---------|-------|------|-------|
| Backend | Node.js / Express 5 (CommonJS) | 3000 | `backend/server.js` → `backend/app.js` |
| Frontend | React 19 / Vite 8 (ESM) | 5173 | `frontend/src/main.jsx` |
| AI Service | Python / FastAPI / PyTorch VAE | 8000 | `ai-service/app.py` |

- **Database**: PostgreSQL (`sistem_arsip_digital`). Reference schema: `database/schema.sql`. Manual migrations in `database/migrations/` — not automated.
- **Frontend also has Electron** support: `frontend/electron/main.js` (`npm run electron`).
- Backend auto-applies schema alterations on startup (`ensureIntegrityColumns`, `app.js:18-70`) — running the server can modify the DB.
- **No test framework** in backend or frontend. AI service has ad-hoc scripts (`test_fastapi_app.py`, `test_predict_endpoint.py`) requiring the service running.
- Root-level scratch artifacts (`tmp-*.json`, `audit-*.pdf/doc`, `gcm-diagnose.log`) are gitignored junk — ignore them. Root `TODO.md` is stale (its bcrypt issue is already fixed).

## Running the Services

### Backend
```bash
cd backend
# Create .env: DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD, JWT_SECRET, PORT
npm install
node server.js        # or: npm run dev (both run server.js)
```
- Requires PostgreSQL running.
- `.env` exists locally but is gitignored — never commit real credentials.
- **`package-lock.json` is gitignored** for all services — don't try to commit it or rely on lockfile pinning.
- `nodemon` is a devDependency but the `dev` script still runs `node server.js`.

### Frontend
```bash
cd frontend
npm install
npm run dev           # Vite dev server on :5173
npm run lint          # ESLint (the only check available)
```
- API URL defaults to `http://localhost:3000` (`src/services/apiService.js:3`), override with `VITE_API_URL`.
- `npm run electron` launches the desktop app; `npm run build` for production.

### AI Service
```bash
cd ai-service
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
# Create .env: HOST, PORT, DATABASE, USER, PASSWORD (DB_HOST/DB_* also accepted as fallback)
uvicorn app:app --host 0.0.0.0 --port 8000
```
- Endpoints: `/health`, `/predict`. Reads from `audit_log` table, scores via VAE reconstruction error vs threshold in `models/deployment_config.json`.
- Training: `python train_vae_pytorch.py` (current). Preprocessing: `python preprocessing.py`.
- Model artifacts live in `ai-service/models/` (active) and `ai-service/model/` (legacy).
- `ai-service/stage7/` plus various `validate_*.py`/stage reports are experimental forensic-audit work — not production pipeline.
- `docs/VAE_ARCHITECTURE.md` is an outdated design doc: it says 10 input features, but code enforces 9 (`services/inference.py:26`). Trust the code.

## Code Conventions

### Backend (Node.js)
- CommonJS. Routes in `backend/routes/`, controllers in `backend/controllers/`, services in `backend/services/`.
- Middleware: `authMiddleware.js` (JWT via `jsonwebtoken`), `roleMiddleware.js` (`authorizeRoles`). TOTP 2FA via `speakeasy`.
- All mutating operations write to `audit_log` via `auditLogService`.
- Master-data endpoints are mounted at **root level** (`/jaksa`, `/jenis-pidana`, `/instansi-penyidik`, `/jenis-perkara/:id`) AND under `/api` (`app.js:87-89`) — not everything lives under `/api`.
- Uploaded files are stored on disk in `backend/uploads/` (auto-created), not the database. PDF-only filter, timestamped sanitized filenames.
- Email validation/normalization: `backend/utils/accountSecurity.js`. `generateHash.js` is a one-off bcrypt script.

### Frontend (React)
- Functional components, React Router v7. Role gate: `RequireRole` in `src/routes/AppRoutes.jsx`.
- Roles `admin`, `arsiparis`, `user` are **case-insensitive** end-to-end (backend normalizes to lowercase before comparing).
- Auth state in `localStorage`: `token`, `role`, `pendingAuthToken` (2FA flow: login → OTP verification → token activated).
- API layer: `src/services/apiService.js` (axios instance with auth interceptor).

### AI Service (Python)
- FastAPI; Pydantic schemas in `schemas/`, inference in `services/inference.py`, model loading in `services/model_loader.py`.
- VAE input shape is strictly `(n, 9)` — enforced at runtime.
- `config.py` defaults `MODEL_PATH` etc. to legacy `model/*.keras`; runtime hardcodes PyTorch `models/` instead — config env vars for model paths are effectively unused.

## Known Issues

- `ai-service/requirements.txt` lists TensorFlow but production inference uses PyTorch — `torch` is missing from requirements entirely; install manually if needed.
- Backend `app.js` runs `ALTER TABLE`/`CREATE TABLE IF NOT EXISTS` on every startup — intentional but unusual.

## Database Notes

- `database/schema.sql` is documentation, not a migration runner. Migrations in `database/migrations/` must be applied manually (startup auto-DDL only covers some columns).
- Roles seeded in `roles` table: admin, arsiparis, user.
- Audit log chaining: each entry has `hash_sebelumnya` and `hash_entri` for tamper-evidence; integrity verification history in `verifikasi_integritas_berkas`.
