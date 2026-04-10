# LogiTrack — Environment Variables Reference

All configuration is supplied through environment variables (or a `.env` file at the project root).  
Copy `.env.example` → `.env` and fill in the required values before starting any service.

> **Security rule:** Never commit `.env`, `.env.development`, or any file containing real credentials.  
> The repository ships only `.env.example` with safe placeholder values.

---

## Variable Reference

### PostgreSQL

| Variable | Required | Default | Description |
|---|---|---|---|
| `POSTGRES_USER` | ✅ | — | PostgreSQL superuser / application user name |
| `POSTGRES_PASSWORD` | ✅ | — | PostgreSQL superuser password |
| `POSTGRES_DB` | ✅ | — | Primary application database name |
| `POSTGRES_PORT` | ✴️ | `5432` | Host-side port mapping for the container |
| `DATABASE_URL` | ✅ | — | Async DSN: `postgresql+asyncpg://user:pass@host:port/db` |
| `DATABASE_SYNC_URL` | ✅ | — | Sync DSN for Alembic/ETL: `postgresql+psycopg2://user:pass@host:port/db` |
| `MLFLOW_DB` | ✴️ | `mlflow` | Logical database inside Postgres used by the MLflow tracking server |

### Security / Auth

| Variable | Required | Default | Description |
|---|---|---|---|
| `SECRET_KEY` | ✅ | — | 64-character hex string used to sign JWT tokens.  Generate: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `ALGORITHM` | ✴️ | `HS256` | JWT signing algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | ✴️ | `30` | Lifetime of short-lived access tokens (minutes) |
| `REFRESH_TOKEN_EXPIRE_DAYS` | ✴️ | `7` | Lifetime of refresh tokens (days) |
| `CORS_ORIGINS` | ✴️ | `http://localhost:5173,http://localhost:3000` | Comma-separated list of allowed CORS origins.  Use `*` only in development. |

### Redis

| Variable | Required | Default | Description |
|---|---|---|---|
| `REDIS_PASSWORD` | ✅ (prod) | — | Redis authentication password (set via `requirepass` in the container command) |
| `REDIS_PORT` | ✴️ | `6379` | Host-side port mapping for the Redis container |
| `REDIS_URL` | ✴️ | `None` | Full Redis connection URL: `redis://:password@host:6379/0`.  When unset the backend uses an in-memory rate-limit store (single process, non-persistent). |

### MinIO (S3-compatible Object Storage)

| Variable | Required | Default | Description |
|---|---|---|---|
| `MINIO_ROOT_USER` | ✅ | — | MinIO admin username (Docker container env) |
| `MINIO_ROOT_PASSWORD` | ✅ | — | MinIO admin password (Docker container env) |
| `MINIO_API_PORT` | ✴️ | `9000` | Host-side port for the MinIO S3 API |
| `MINIO_CONSOLE_PORT` | ✴️ | `9001` | Host-side port for the MinIO web console |
| `S3_ENDPOINT_URL` | ✅ | — | Full URL the application uses to reach MinIO/S3 (e.g. `http://minio:9000` inside Docker, `http://localhost:9000` locally) |
| `S3_ACCESS_KEY` | ✅ | — | S3/MinIO access key ID |
| `S3_SECRET_KEY` | ✅ | — | S3/MinIO secret access key |
| `S3_BUCKET_NAME` | ✴️ | `logitrack` | Target bucket for ML model artefacts and PDF reports |

### MLflow

| Variable | Required | Default | Description |
|---|---|---|---|
| `MLFLOW_TRACKING_URI` | ✴️ | `http://localhost:5050` | URI the backend uses to log experiments to the MLflow tracking server |
| `MLFLOW_PORT` | ✴️ | `5050` | Host-side port mapping for the MLflow UI container |

### Adminer (development only)

| Variable | Required | Default | Description |
|---|---|---|---|
| `ADMINER_PORT` | ✴️ | `8080` | Host-side port for the Adminer database inspection UI |

### ML / Prediction

| Variable | Required | Default | Description |
|---|---|---|---|
| `ALERT_THRESHOLD` | ✴️ | `0.65` | Probability cut-off above which a shipment is flagged as at-risk.  Range: `[0.0, 1.0]`. |

### ETL

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATA_RAW_PATH` | ✴️ | `data/raw` | Relative path (from project root) to the directory containing the 9 Olist CSV files |

### Runtime

| Variable | Required | Default | Description |
|---|---|---|---|
| `ENVIRONMENT` | ✴️ | `development` | One of `development`, `staging`, `production`.  Controls SQL echo, HTTPS enforcement, and HSTS headers. |

---

## Profiles and `.env` file usage

| Context | `.env` file to use |
|---|---|
| Local development | Copy `.env.example` → `.env`; or use `.env.development` directly |
| Docker Compose dev | `docker compose --profile dev up -d` reads `.env` automatically |
| Docker Compose prod | `docker compose --profile prod up -d` reads `.env` automatically |
| CI (GitHub Actions) | All vars set as repository secrets / workflow `env:` block |

---

## Generating secrets

```bash
# SECRET_KEY (64-char hex)
python -c "import secrets; print(secrets.token_hex(32))"

# POSTGRES_PASSWORD / REDIS_PASSWORD / MINIO_ROOT_PASSWORD
python -c "import secrets; print(secrets.token_urlsafe(24))"
```

---

✅ = required, no safe default available  
✴️ = optional, has a safe default
