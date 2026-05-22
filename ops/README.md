# Mishkaat — Operations runbook

This folder ships the **infrastructure templates** to deploy Mishkaat safely.
None of these files contain real secrets — fill them in with your values before use.

```
ops/
├── nginx.conf                  # Reverse proxy, TLS, security headers, rate-limits
├── proxy-headers.conf          # Shared headers for /api/ locations
├── mongo-init.js               # First-boot creation of a scoped (non-root) DB user
├── mishkaat.service            # systemd unit for the API (sandboxed)
├── mishkaat-backup.service     # systemd one-shot for backups
├── mishkaat-backup.timer       # systemd timer — runs the backup daily
├── backup.sh                   # mongodump → gpg encrypt → rotate
└── restore.sh                  # gpg decrypt → mongorestore
```

Plus, at the repo root:
- [docker-compose.yml](../docker-compose.yml) — full stack (Nginx + app + Mongo) on isolated networks
- [backend/Dockerfile](../backend/Dockerfile) — non-root, healthchecked
- [backend/.env.example](../backend/.env.example) — env template

---

## A. Deploy via Docker Compose (simplest)

1. Copy `backend/.env.example` → `backend/.env` and fill **every** field.
2. Also create a top-level `.env` next to `docker-compose.yml` containing:
   ```env
   MONGO_ROOT_USER=root
   MONGO_ROOT_PASSWORD=<strong, random>
   MONGO_APP_USER=mishkaat
   MONGO_APP_PASSWORD=<strong, random — referenced by MONGO_URL in backend/.env>
   DB_NAME=quran_center
   ```
3. Put your TLS cert and key into `ops/tls/`:
   ```
   ops/tls/fullchain.pem
   ops/tls/privkey.pem
   ```
   For Let's Encrypt, mount `certbot` separately and run a renewal job (out of scope here).
4. Replace `app.your-domain.example` in `ops/nginx.conf` with your real hostname.
5. Bring up:
   ```bash
   docker compose pull
   docker compose up -d --build
   ```
6. Watch the first boot — you'll see the admin password line **once** if you didn't set `INITIAL_ADMIN_PASSWORD`:
   ```bash
   docker compose logs -f app
   ```

### Network topology Docker Compose gives you
```
Internet ──TLS──▶ nginx ──[public network]──▶  app  ──[internal-only network]──▶ mongo
                          (host port 443)         (no published port)              (no published port)
```
Mongo and the app are unreachable from the internet by construction.

---

## B. Deploy on a single VPS (systemd, no Docker)

1. Layout on disk:
   ```
   /opt/mishkaat/
   ├── backend/                 ← clone of the backend folder
   ├── venv/                    ← python -m venv venv && venv/bin/pip install -r backend/requirements.txt
   └── ops/                     ← clone of this folder
   /etc/mishkaat/
   ├── mishkaat.env             ← copy of backend/.env (mode 600, owner root)
   └── backup.env               ← env for the backup service
   ```
2. Install the systemd units:
   ```bash
   sudo install -m 644 ops/mishkaat.service        /etc/systemd/system/
   sudo install -m 644 ops/mishkaat-backup.service /etc/systemd/system/
   sudo install -m 644 ops/mishkaat-backup.timer   /etc/systemd/system/
   sudo install -m 750 ops/backup.sh               /opt/mishkaat/ops/
   sudo systemctl daemon-reload
   sudo systemctl enable --now mishkaat.service mishkaat-backup.timer
   ```
3. Install Nginx:
   ```bash
   sudo install -m 644 ops/nginx.conf        /etc/nginx/nginx.conf
   sudo install -m 644 ops/proxy-headers.conf /etc/nginx/proxy-headers.conf
   sudo nginx -t && sudo systemctl reload nginx
   ```

### Sandboxing the systemd units give you
The `mishkaat.service` unit runs the API under `DynamicUser` with `NoNewPrivileges`, no write access outside `/tmp`, no kernel-tunable access, and an outbound network whitelist locked to localhost (Mongo). The `mishkaat-backup.service` is similarly constrained and only has write access to `/var/backups/mishkaat`.

---

## C. Backups

### What `backup.sh` does
- Pipes `mongodump --archive --gzip` straight into `gpg --encrypt` so **plaintext never touches the disk**.
- Encrypted file: `/var/backups/mishkaat/mishkaat-YYYYMMDDTHHMMSSZ.archive.gpg`, mode 600.
- Rotates: keeps the last 30 days (configurable via `RETENTION_DAYS`).
- If `RCLONE_REMOTE` is set, also ships off-host via `rclone copy`.

### Setting up
1. Generate a backup-only GPG keypair (so the production host only holds the **public** key — the private key lives off-host with the operator):
   ```bash
   gpg --batch --quick-generate-key 'Mishkaat Backup <ops@your-domain>' rsa4096 default 5y
   gpg --armor --export 'Mishkaat Backup' > backup-public.asc
   # Move backup-public.asc to the prod host:
   sudo -u mishkaat-backup gpg --import backup-public.asc
   ```
2. Create `/etc/mishkaat/backup.env`:
   ```env
   MONGO_URI=mongodb://mishkaat:<pwd>@127.0.0.1:27017/quran_center?authSource=quran_center
   BACKUP_DIR=/var/backups/mishkaat
   GPG_RECIPIENT=Mishkaat Backup
   RETENTION_DAYS=30
   # Optional:
   # RCLONE_REMOTE=offsite:mishkaat-backups
   ```
3. The timer fires every day at 03:17 UTC. Test once manually:
   ```bash
   sudo systemctl start mishkaat-backup.service
   sudo journalctl -u mishkaat-backup.service -n 50 --no-pager
   ```

### Restore drill — DO THIS BEFORE YOU NEED IT
On a staging host that has the **private** key:
```bash
MONGO_URI=mongodb://... ./ops/restore.sh mishkaat-20260522T031700Z.archive.gpg
```
If the script prompts for `RESTORE` and the import succeeds, your DR plan works.

---

## D. Secret hygiene checklist

- [ ] `SECRET_KEY` and `PII_ENCRYPTION_KEY` are **per-instance** and stored in your secret manager (1Password, HashiCorp Vault, AWS Secrets Manager, Doppler, etc.) — not just in `.env`.
- [ ] Rotating `PII_ENCRYPTION_KEY` requires a one-time re-encryption pass — plan ahead. The code's `decrypt_pii` is tolerant of legacy plaintext but **not** of a wrong key.
- [ ] The GPG **private** backup key does NOT live on the production host.
- [ ] TLS cert renewal is automated (Let's Encrypt + cron, certbot, or your CDN).
- [ ] `git check-ignore .env` returns 0 (the file is ignored) — verify before every commit.

---

## E. Health monitoring

The app exposes `GET /api/health` (unauthenticated, returns 200/`{"status":"healthy"}`). Wire your uptime monitor to this and to `https://app.your-domain.example/` to detect Nginx+TLS issues separately.

For deeper observability, watch:
- `db.audit_logs` for `LOGIN_FAILED` spikes (brute-force) and `PUBLIC_REGISTER_CENTER` spikes (registration spam).
- The `mishkaat-backup.service` journal — alert if it hasn't run in > 26 hours.
- Mongo storage usage — TTL collections (`revoked_tokens`, `login_attempts`, `register_attempts`) should stay small (< 10k docs).
