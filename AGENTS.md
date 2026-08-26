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
- **Backend ↔ AI coupling**: every audit-log insert (`backend/services/auditLogService.js`) POSTs synchronously to the AI service `/predict` (default `http://127.0.0.1:8000`, override with `AI_SERVICE_URL`) and inserts into `laporan_anomali` on an ANOMALY response. Scoring is skipped without a valid IPv4; AI errors are logged, never thrown.
- Backend auto-applies schema alterations on startup (`ensureIntegrityColumns`, `app.js:19-73`) — running the server can modify the DB.
- **No test framework** in backend or frontend. AI service has ad-hoc scripts (`test_fastapi_app.py`, `test_predict_endpoint.py`) requiring the service + Postgres running.
- Root-level scratch artifacts (`tmp-*.json`, `audit-*.pdf/doc`, `gcm-diagnose.log`) are gitignored junk — ignore them. Root `TODO.md` is stale (bcrypt duplicate in `userController.js` was already fixed).

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
# .env: HOST, PORT, DATABASE, USER, PASSWORD (DB_HOST/DB_* accepted as fallback)
uvicorn app:app --host 0.0.0.0 --port 8000
```
- Endpoints: only `/health` and `/predict`. Startup fails fast if final model artifacts are incomplete or mismatched.
- **Active path**: `app.py` → `services/inference.py` (compat shim) → `services/final_vae_pipeline.py`. Raw audit-log payload → Stage 2 preprocessing contract → PyTorch VAE reconstruction error vs threshold.
- Artifacts live in `models/final_vae/` (`vae_model_final.pth`, `model_config.json`, `model_metadata.json`, `threshold.json`). Threshold = P95 of train-normal scores from `threshold.json` — **not** `models/deployment_config.json` (that's the frozen legacy threshold `3.149629`, only referenced by forensic scripts).
- The loaded artifact must pair with preprocessing contract `stage2-final-v2-bounded-ip-zscore`; SSOT data in `dataset/final_stage1_ssot/`. Mismatch raises at startup/predict.
- Training: `python train_vae_pytorch.py` (writes `models/final_vae/`, validates expected split sizes train=6692/validation=4168/test=4140). Stage 2 contract prep: `finalize_preprocessing_stage2.py`.

## Code Conventions

### Backend (Node.js)
- CommonJS. Routes in `backend/routes/`, controllers in `backend/controllers/`, services in `backend/services/`, middleware in `backend/middleware/` (`authMiddleware.js` JWT, `roleMiddleware.js` `authorizeRoles`). TOTP 2FA via `speakeasy`.
- All mutating operations write to `audit_log` via `auditLogService` (which also triggers AI scoring, see above).
- All routes live at **root level** (`/users`, `/lemari`, `/rak`, `/perkara`, `/berkas`, `/peminjaman`, `/auth`, `/totp`, `/audit-log`, `/replication`, plus master data) because the frontend axios `baseURL` has no `/api` prefix. Only `perkara` and master-data are *additionally* duplicated under `/api` (`app.js:92-93`) — new routes must be mounted at root or the frontend can't reach them.
- Uploaded files go to disk in `backend/uploads/berkas` and `backend/uploads/covers` (auto-created), PDF-only filter (mimetype + extension).
- Ignore the `*_legacy_pre_*.js` copies (`app_legacy_pre_audit_context.js`, `auditLogService_legacy_pre_final.js`, `auditLogService_pre_request_context.js`) — edit the non-suffixed files.
- Email validation/normalization: `backend/utils/accountSecurity.js`. `generateHash.js` is a one-off bcrypt script.

### Frontend (React)
- Functional components, React Router v7. Role gate: `RequireRole` in `src/routes/AppRoutes.jsx`.
- Roles `admin`, `arsiparis`, `user` are **case-insensitive** end-to-end (backend normalizes to lowercase before comparing).
- Auth state in `localStorage`: `token`, `role`, `pendingAuthToken` (2FA flow: login → OTP verification → token activated).
- API layer: `src/services/apiService.js` (axios instance with auth interceptor).

### AI Service (Python)
- VAE input shape is strictly `(n, 9)` — features: `user_id, activity, status, device, ip_address, duration_ms, object_count, hour, day_of_week` (`utils/final_preprocessing_contract.py`); enforced at runtime in `final_vae_pipeline.reconstruction_details`.
- Request schema uses Indonesian field names (`waktu`, `aksi`, `durasi_ms`, `jumlah_objek`, …) — see `schemas/predict_request.py`; extra fields ignored.
- `config.py` defaults `MODEL_PATH` etc. to legacy `model/*.keras` — unused by the active pipeline. Server binds via `API_HOST`/`API_PORT` env vars (uvicorn flags override anyway).
- `/health` endpoint now correctly reports `preprocessing_contract: "stage2-final-v2-bounded-ip-zscore"` (fixed — previously stale).

## Known Issues

- `ai-service/requirements.txt` still lists TensorFlow, unused by the active PyTorch pipeline (`torch` itself is listed, so plain `pip install -r requirements.txt` works).
- Backend `app.js` runs `ALTER TABLE`/`CREATE TABLE IF NOT EXISTS` on every startup — intentional but unusual.
- **Stale docs — trust the code**: `ai-service/README.md` describes the retired Keras pipeline (`train.py`, `model/*.keras`, plus `/retrain`, `/evaluate`, `/model-info` endpoints that no longer exist). `docs/VAE_ARCHITECTURE.md` says 10 input features; code enforces 9.

## Experimental/Legacy Zones — Don't Wire Into Production

- `ai-service`: `*_legacy_pre_final*`, `app_legacy_pre_final.py` (contains the removed `/predict-stage11` route), `models/retrained/`, `models/candidate/`, root `models/vae_model.pth`, `backup_before_*/`, `stage7/`, `validate_*.py` and stage reports.
- Production `/predict` must stay unchanged; candidates stay disconnected until explicitly promoted.

## Database Notes

- `database/schema.sql` is documentation, not a migration runner. Migrations in `database/migrations/` must be applied manually (startup auto-DDL only covers some columns).
- Role names `admin`, `arsiparis`, `user` are fixed by convention; the `roles` table must be seeded manually (no seed SQL in repo).
- Audit log chaining: each entry has `hash_sebelumnya` and `hash_entri` for tamper-evidence (`verifyAuditChain` recomputes them); integrity verification history in `verifikasi_integritas_berkas`.
