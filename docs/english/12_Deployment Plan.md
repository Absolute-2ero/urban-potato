# Deployment Plan

**Version:** v1.1
**Last Updated:** 2026-05-25

---

## 1. Current Deployment Topology

```
Single-server deployment (Linux Server / local dev machine)

┌─────────────────────────────────────────────────────────┐
│  Process: uvicorn (FastAPI)          :8000  HTTP/HTTPS  │
│  Process: nginx (static file server) :80 / :443         │
│  Process: PostgreSQL 16              :5432               │
│  Process: Elasticsearch 8.x          :9200               │
│  Process: Redis 7                    :6379               │
│  File:    data/food_db.sqlite         ./data/  (read-only) │
│  File:    backend/.env (chmod 600)    ./backend/         │
└─────────────────────────────────────────────────────────┘
```

---

## 2. Environment Requirements

| Component | Version | Notes |
|-----------|---------|-------|
| OS | Ubuntu 22.04 LTS | Recommended; Debian 11+ also works |
| Python | 3.11+ | Backend runtime |
| Node.js | 18+ | Frontend build |
| PostgreSQL | 16+ | Primary user data database |
| Elasticsearch | 8.x | Requires IK Chinese analyser plugin |
| Redis | 7+ | Caching service |
| nginx | 1.24+ | Static files + reverse proxy |
| Playwright Chromium | Auto-downloaded | Used by the Dianping crawler |
| Disk space (minimum) | 20 GB | ES index + PG data + logs |
| RAM (minimum) | 4 GB | ES default JVM heap is 1 GB |

---

## 3. Directory Structure (Deployment Root)

```
/opt/macrobite/
├── backend/
│   ├── main.py
│   ├── .env                        ← Sensitive config (chmod 600, not in version control)
│   ├── requirements.txt
│   ├── config/
│   │   └── ranking.yaml            ← Ranking weight configuration
│   └── data/
│       ├── food_db.sqlite          ← Static food database (read-only at runtime)
│       ├── food_seed.json          ← Static food data source
│       └── diet_synonyms.txt       ← ES synonym file
├── frontend/
│   └── dist/                       ← Output of `npm run build` (served by nginx)
└── logs/
    ├── app.log
    └── crawler.log
```

---

## 4. Deployment Steps

### 4.1 Install Dependencies

```bash
# Python environment
python3.11 -m venv /opt/macrobite/venv
source /opt/macrobite/venv/bin/activate
pip install -r backend/requirements.txt

# Playwright browser
playwright install chromium
playwright install-deps chromium

# Frontend build
cd frontend
npm ci
npm run build
```

### 4.2 Elasticsearch Setup

```bash
# Install ES (Ubuntu)
wget https://artifacts.elastic.co/downloads/elasticsearch/elasticsearch-8.x.x-amd64.deb
dpkg -i elasticsearch-8.x.x-amd64.deb

# Install IK Chinese analyser plugin (required — without it, Chinese search won't tokenise correctly)
/usr/share/elasticsearch/bin/elasticsearch-plugin install \
    https://release.infinilabs.com/analysis-ik/stable/elasticsearch-analysis-ik-8.x.x.zip

# Copy synonym file to ES config directory
cp backend/data/diet_synonyms.txt \
    /etc/elasticsearch/analysis/diet_synonyms.txt

# Start and enable
systemctl enable elasticsearch
systemctl start elasticsearch

# Verify
curl http://localhost:9200/_cluster/health
```

### 4.3 Database Initialisation

```bash
# PostgreSQL
sudo -u postgres psql <<EOF
CREATE USER macrobite WITH PASSWORD 'your_password';
CREATE DATABASE macrobite OWNER macrobite;
\c macrobite
EOF

# Run schema migration
cd backend
python -m db.migrate   # Executes schema.sql to create all tables
```

```sql
-- schema.sql (excerpt)
CREATE TABLE users (
    id              SERIAL PRIMARY KEY,
    username        VARCHAR(64) UNIQUE NOT NULL,
    password_hash   VARCHAR(256) NOT NULL,
    email           VARCHAR(128) UNIQUE,
    created_at      TIMESTAMPTZ DEFAULT now(),
    last_login_at   TIMESTAMPTZ
);

CREATE TABLE diet_profiles (
    user_id         INT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    diet_labels     TEXT[] DEFAULT '{}',
    allergens       TEXT[] DEFAULT '{}',
    calorie_goal    INT,
    protein_goal_g  FLOAT,
    fat_goal_g      FLOAT,
    carb_goal_g     FLOAT,
    price_pref      SMALLINT,
    cuisine_prefs   TEXT[] DEFAULT '{}',
    updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE user_food_items (
    id              SERIAL PRIMARY KEY,
    user_id         INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name_zh         VARCHAR(128) NOT NULL,
    name_en         VARCHAR(128),
    calories        FLOAT NOT NULL,
    protein_g       FLOAT NOT NULL DEFAULT 0,
    fat_g           FLOAT NOT NULL DEFAULT 0,
    carb_g          FLOAT NOT NULL DEFAULT 0,
    sodium_mg       FLOAT,
    fiber_g         FLOAT,
    diet_labels     TEXT[] DEFAULT '{}',
    source          VARCHAR(16) NOT NULL DEFAULT 'user',
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ
);
CREATE INDEX idx_user_food_items_user ON user_food_items(user_id);

CREATE TABLE food_log_entries (
    id              SERIAL PRIMARY KEY,
    user_id         INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    log_date        DATE NOT NULL,
    meal_type       VARCHAR(16) NOT NULL,
    food_id         INT,                    -- References SQLite food_items (static); NULL if user source
    user_food_id    INT REFERENCES user_food_items(id) ON DELETE SET NULL,
                                            -- References user_food_items; NULL if static source
    food_name       VARCHAR(128) NOT NULL,  -- Denormalised snapshot; preserved on edit/delete
    quantity_g      FLOAT NOT NULL,
    calories_kcal   FLOAT NOT NULL,
    protein_g       FLOAT,
    fat_g           FLOAT,
    carb_g          FLOAT,
    created_at      TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT chk_food_source CHECK (
        (food_id IS NOT NULL AND user_food_id IS NULL) OR
        (food_id IS NULL AND user_food_id IS NOT NULL)
    )
);
CREATE INDEX idx_food_log_user_date ON food_log_entries(user_id, log_date);

CREATE TABLE saved_restaurants (
    id              SERIAL PRIMARY KEY,
    user_id         INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    restaurant_id   VARCHAR(64) NOT NULL,
    restaurant_name VARCHAR(256) NOT NULL,
    saved_at        TIMESTAMPTZ DEFAULT now(),
    UNIQUE(user_id, restaurant_id)
);

CREATE TABLE search_feedbacks (
    id              SERIAL PRIMARY KEY,
    user_id         INT REFERENCES users(id),
    query_text      TEXT NOT NULL,
    restaurant_id   VARCHAR(64) NOT NULL,
    restaurant_name VARCHAR(256),
    rank_position   SMALLINT,
    is_relevant     BOOLEAN NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT now()
);
```

### 4.4 Elasticsearch Index Initialisation

```bash
cd backend
python -m ir.index_builder --create-index              # Create index (define mapping)
python -m crawler.pipeline --city Beijing --source gaode --limit 500  # Seed initial data
```

### 4.5 Environment Variables

```bash
# backend/.env (chmod 600)
POSTGRES_DSN=postgresql+asyncpg://macrobite:your_password@localhost/macrobite
REDIS_URL=redis://localhost:6379/0
ELASTICSEARCH_URL=http://localhost:9200
GAODE_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxx
SESSION_SECRET=generate_a_sufficiently_random_string_at_least_32_chars
ES_INDEX_NAME=restaurants
```

> **Note:** LLM API keys (`DEEPSEEK_API_KEY`, `LLM_MODEL`) are only required when running the crawler pipeline and are not part of the runtime backend config. Configure them separately in the crawler environment before running `crawler/pipeline.py`.

Generate a random session secret:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 4.6 nginx Configuration

```nginx
# /etc/nginx/sites-available/macrobite
server {
    listen 80;
    server_name your_domain.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name your_domain.com;

    ssl_certificate     /etc/letsencrypt/live/your_domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your_domain.com/privkey.pem;

    # Frontend static files
    root /opt/macrobite/frontend/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;   # SPA fallback
    }

    # API reverse proxy
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_cookie_flags ~ httponly samesite=lax;
    }
}
```

### 4.7 systemd Service

```ini
# /etc/systemd/system/macrobite.service
[Unit]
Description=MacroBite FastAPI Backend
After=network.target postgresql.service elasticsearch.service redis.service

[Service]
User=www-data
WorkingDirectory=/opt/macrobite/backend
EnvironmentFile=/opt/macrobite/backend/.env
ExecStart=/opt/macrobite/venv/bin/uvicorn main:app \
    --host 127.0.0.1 \
    --port 8000 \
    --workers 4 \
    --access-log \
    --log-level info
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload
systemctl enable macrobite
systemctl start macrobite
systemctl status macrobite
```

---

## 5. Local Development Setup

```bash
# Start all dependency services (Docker Compose)
docker compose up -d postgres elasticsearch redis

# Backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # Fill in local config values
uvicorn main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev   # Visit http://localhost:3000
```

`docker-compose.yml` excerpt:
```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: macrobite
      POSTGRES_PASSWORD: dev_password
      POSTGRES_DB: macrobite
    ports: ["5432:5432"]

  elasticsearch:
    image: elasticsearch:8.13.0
    environment:
      - discovery.type=single-node
      - ES_JAVA_OPTS=-Xms512m -Xmx512m
      - xpack.security.enabled=false
    ports: ["9200:9200"]

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
```

---

## 6. Common Operations

```bash
# Stream backend logs
journalctl -u macrobite -f

# Rebuild ES index (data unchanged, mapping rebuilt)
python -m ir.index_builder --rebuild

# Manually trigger a city crawl
python -m crawler.pipeline --city Shanghai --source all --limit 300

# Back up PostgreSQL
pg_dump -U macrobite macrobite > backup_$(date +%Y%m%d).sql

# Back up food database (SQLite)
cp data/food_db.sqlite backups/food_db_$(date +%Y%m%d).sqlite

# Restart the backend service
systemctl restart macrobite
```

---

## 7. Backup Strategy

| Data | Frequency | Storage | Retention |
|------|-----------|---------|-----------|
| PostgreSQL full dump | Daily at 02:00 | Local + remote storage | 30 days |
| food_db.sqlite | When the static library seed data is updated and rebuilt | Local | 10 versions |
| ES index | Weekly snapshot (Elasticsearch Snapshot API) | Local | 4 weeks |
| `.env` | Once, manually after initial setup | Encrypted offline storage | Permanent |

```bash
# Automated backup via crontab
0 2 * * * pg_dump -U macrobite macrobite | gzip > /backups/pg_$(date +\%Y\%m\%d).sql.gz
```