# Production Deployment Guide: PikaNews Aggregator

This guide provides step-by-step instructions for deploying the PikaNews Aggregator, API server, and automated scraper into production environments.

---

## Architecture Overview

The system consists of the following components:
1. **FastAPI Web Server**: Exposes REST endpoints (`/latest`, `/search`, `/api/stats`) and serves the glassmorphic Command Center UI.
2. **Ingestion Engine**: Python scrapers running via Typer CLI (`python cli/main.py scrape`).
3. **Database (PostgreSQL or SQLite)**: Stores article metadata, body content, and spaCy-extracted named entities.
4. **Redis Cache (Optional)**: Bypasses database queries for frequent search terms and latest indices.
5. **Scheduler (Optional)**: Can run inside a container to scrape local updates, though **GitHub Actions** is the recommended serverless scheduler.

---

## Option A: Docker Compose Deployment (Recommended)

This setup deploys the FastAPI application, a PostgreSQL database, and a Redis caching server on a Linux VPS (Ubuntu).

### 1. Provision a VPS & Install Docker
Ensure your server has Docker and Docker Compose installed. On Ubuntu:
```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose
sudo systemctl enable --now docker
```

### 2. Configure Environment Variables
Create a production `.env` file in your workspace directory:
```ini
# Production Environment Variables
CONFIG_PATH=config.yaml
SQLITE_PATH=pikanews.db
REDIS_URL=redis://redis:6379/0
POSTGRES_URL=postgresql://postgres:SecurePassword99@db:5432/pikanews
OLLAMA_HOST=http://host.docker.internal:11434
OLLAMA_MODEL=llama3
```

### 3. Review Docker Compose
The included [docker-compose.yml](file:///e:/sarthi/docker-compose.yml) starts Postgres, Redis, the FastAPI backend, and a scheduler container:
```bash
# Launch the stack in detached background mode
docker-compose up -d --build
```

### 4. Connect GitHub Actions Scraper to Production
If using PostgreSQL, the GitHub Actions scraping pipeline can insert new articles directly into your production database:
1. Go to your **GitHub Repository** -> **Settings** -> **Secrets and variables** -> **Actions**.
2. Click **New repository secret**.
3. Name: `POSTGRES_URL`.
4. Value: `postgresql://postgres:SecurePassword99@<YOUR_SERVER_IP>:5432/pikanews` (ensure port `5432` is open or restricted to GitHub Runner IP ranges on your firewall).

Once configured, every daily run of the GitHub Actions scraper will push freshly scraped articles straight into your production app!

---

## Option B: SQLite Git-Sync Deployment (PaaS-friendly)

If you prefer a lightweight, free-tier deployment (e.g., Render, Railway, Fly.io) without managing databases:

1. **GitHub Actions commits SQLite**: The `.github/workflows/scrape.yml` workflow scrapes websites, builds the SQLite `pikanews.db`, and commits it directly back to your GitHub repo daily.
2. **PaaS Auto-Deploy**:
   - Link your hosting provider (Render/Railway) to your GitHub repository.
   - Configure it to deploy the Dockerfile or run `pip install -r requirements.txt && uvicorn api.server:app --host 0.0.0.0 --port 8000`.
   - Enable **Auto-Deploy** in Render/Railway. When GitHub Actions pushes the updated `pikanews.db` file, it triggers a redeployment, serving the fresh database automatically.

---

## Option C: Bare-Metal systemd Deployment

To run the FastAPI server directly on the host OS without Docker:

### 1. Create a System User and Clone Code
```bash
sudo useradd -r -s /bin/false pikanews
sudo git clone https://github.com/<your-username>/pikanews.git /opt/pikanews
sudo chown -R pikanews:pikanews /opt/pikanews
```

### 2. Set Up Virtual Environment & Dependencies
```bash
cd /opt/pikanews
sudo -u pikanews python3 -m venv venv
sudo -u pikanews venv/bin/pip install --upgrade pip
sudo -u pikanews venv/bin/pip install -r requirements.txt
sudo -u pikanews venv/bin/python -m playwright install chromium
sudo -u pikanews venv/bin/python -m spacy download en_core_web_sm
```

### 3. Create Systemd Service File
Write the service definition to `/etc/systemd/system/pikanews.service`:
```ini
[Unit]
Description=PikaNews FastAPI Backend
After=network.target

[Service]
User=pikanews
WorkingDirectory=/opt/pikanews
Environment="PATH=/opt/pikanews/venv/bin"
Environment="CONFIG_PATH=config.yaml"
ExecStart=/opt/pikanews/venv/bin/uvicorn api.server:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### 4. Start and Enable Service
```bash
sudo systemctl daemon-reload
sudo systemctl start pikanews
sudo systemctl enable pikanews
```

---

## Reverse Proxy & SSL Configuration (HTTPS)

It is highly recommended to put a reverse proxy in front of FastAPI to handle SSL certificates.

### Option 1: Caddy Server (Easiest, Auto-SSL)
Caddy automatically provisions and renews SSL certificates from Let's Encrypt.

1. Install Caddy on your VPS.
2. Configure `/etc/caddy/Caddyfile`:
```caddy
pikanews.yourdomain.com {
    reverse_proxy 127.0.0.1:8000
}
```
3. Restart Caddy:
```bash
sudo systemctl restart caddy
```

### Option 2: Nginx & Certbot
1. Install Nginx and Certbot:
```bash
sudo apt install nginx certbot python3-certbot-nginx -y
```
2. Write Nginx Virtual Host config to `/etc/nginx/sites-available/pikanews`:
```nginx
server {
    server_name pikanews.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```
3. Enable configuration & reload Nginx:
```bash
sudo ln -s /etc/nginx/sites-available/pikanews /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl restart nginx
```
4. Request SSL certificate:
```bash
sudo certbot --nginx -d pikanews.yourdomain.com
```

---

## Database Backups

If running on Docker Compose PostgreSQL, set up a daily backup cron job:
```bash
# Add to crontab -e
0 2 * * * docker exec pikanews_db pg_dump -U postgres pikanews > /opt/backups/pikanews_$(date +\%F).sql
```
