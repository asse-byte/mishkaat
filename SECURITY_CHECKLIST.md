# 🛡️ Mishkaat — Pre-Onboarding Security Checklist
## دليل الأمان التشغيلي قبل استقبال مركز تحفيظ جديد

> **Purpose**: Walk through this list **once per center** before granting access. The platform holds personal data of minors — assume the strictest privacy regime.
>
> **Audit baseline**: 2026-05-22 (see [PRODUCTION_HEALTH_REPORT.md](PRODUCTION_HEALTH_REPORT.md))

---

## 0. Pre-flight: Confirm the Latest Audit Applied

- [ ] `git log --oneline -n 5` shows the audit commit.
- [ ] `grep -c "AUDIT-2026-05-22" backend/server.py` returns **≥ 75**.
- [ ] `python -c "import ast; ast.parse(open('backend/server.py').read())"` exits cleanly.
- [ ] `python -c "from cryptography.fernet import Fernet; print('OK')"` succeeds (dependency installed).

---

## 1. `.env` — Required Variables

The application now **refuses to boot in production** with the default secret or without an admin bootstrap password. Set:

```env
APP_ENV=production
SECRET_KEY=<run: python -c "import secrets; print(secrets.token_hex(64))">
PII_ENCRYPTION_KEY=<run: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())">
INITIAL_ADMIN_PASSWORD=<strong, ≥12 chars, will be set on the admin user>
MONGO_URL=mongodb://user:pass@127.0.0.1:27017
DB_NAME=quran_center
ALLOWED_ORIGINS=https://mishkaat-app.com
SEED_DEMO_DATA=false                  # default; never true in production
BCRYPT_ROUNDS=12                      # default; can raise to 13/14 if CPU allows
ACCESS_TOKEN_EXPIRE_MINUTES=60        # default; lower for higher-sensitivity deployments
REFRESH_TOKEN_EXPIRE_DAYS=7
```

- [ ] `.env` is **NOT** committed (`git check-ignore .env` returns 0).
- [ ] Each value above is set to a real, strong, **per-instance** secret.

---

## 2. Default / Demo Accounts

- [ ] `SEED_DEMO_DATA` is `false` (default).
- [ ] On first launch, you see the `🔑 GENERATED admin password` line (random) **OR** you set `INITIAL_ADMIN_PASSWORD` in `.env`. In either case, the password is **rotated again** by the admin on first login via `POST /api/auth/change-password`.
- [ ] No `manager1`, `teacher1`, `student1`, `parent1` user exists (`db.users.find({username:{$in:["manager1","teacher1","student1","parent1"]}}).count()` returns 0).

---

## 3. Onboarding a New Center (admin path)

- [ ] Admin creates the center via `POST /api/centers` and supplies the manager credentials.
  Password complexity is enforced server-side (≥8 chars + letter + digit). Communicate via an out-of-band channel.
- [ ] Manager logs in and **changes their password** via `POST /api/auth/change-password`. This bumps `user_version` and invalidates any other sessions automatically.
- [ ] Verify `center_id` linked back on the manager (`db.users.findOne({username:'<mgr>'}).center_id`).
- [ ] If the center came in via `POST /api/public/register-center`, it sits at `approval_status: "pending"` and the manager **cannot log in** until you approve:
  ```
  POST /api/centers/{id}/approve     (admin only)
  POST /api/centers/{id}/reject
  GET  /api/centers/pending
  ```

---

## 4. Multi-Center Isolation Verification (BOLA probes)

Run from the new manager's token. **Every probe below must return 403 or `[]`** — if any returns 200 with data, STOP and re-deploy.

- [ ] `GET /api/centers` → only the new center.
- [ ] `GET /api/students` → only own center.
- [ ] `GET /api/teachers`, `GET /api/halaqat` → only own center.
- [ ] `GET /api/recitations?student_id=<other-center-student>` → 403.
- [ ] `GET /api/recitations` (no params) → own-center scope only.
- [ ] `GET /api/attendance` → only own halaqat.
- [ ] `GET /api/attendance?halaqah_id=<other-center-halaqah>` → 403.
- [ ] `POST /api/attendance` referencing other center's halaqah → 403.
- [ ] `POST /api/recitations` for another center's student → 403.
- [ ] `GET /api/fees` → only own students.
- [ ] `PUT /api/centers/<other_center_id>` → 403.
- [ ] `POST /api/salaries` with `center_id` = other center → 403.
- [ ] `POST /api/review-plans` with `center_id` = other center → 403.
- [ ] `GET /api/review-plans`, `/api/salaries`, `/api/expenses`, `/api/attendance/center` → all scoped to own center.

Then as a `parent` (linked by phone):
- [ ] `GET /api/recitations` → only their child's recitations.
- [ ] `GET /api/fees` → only their child's fees.

As a `student`:
- [ ] `GET /api/recitations`, `/api/fees` → only own data.

---

## 5. JWT / Session Lifecycle

- [ ] Login response includes `access_token`, `refresh_token`, and `expires_in`.
- [ ] Frontend rotates via `POST /api/auth/refresh` with `{refresh_token: ...}` before the 60-minute expiry.
- [ ] Logout (`POST /api/auth/logout`) returns 200 **and** the same access token afterwards returns 401 (revoked).
- [ ] After `POST /api/auth/change-password`, any other previously-issued token from that user returns 401.
- [ ] Disabled user (`is_active=false`) cannot log in **and** cannot use a previously-issued token (both return 403).

---

## 6. PII at-Rest Verification

- [ ] `mongosh quran_center --eval "db.students.findOne({}, {date_of_birth:1, guardian_address:1})"` shows `gAAAAA...` Fernet tokens, **not** plaintext.
- [ ] `GET /api/students` from a manager account returns those same fields **decrypted** (because the manager has the runtime key via `PII_ENCRYPTION_KEY`).
- [ ] `PII_ENCRYPTION_KEY` is backed up to your secret store. Losing it permanently destroys those two fields' contents.

---

## 7. MongoDB Hardening

- [ ] Bound to `127.0.0.1` or VPC-internal only.
- [ ] DB user role scoped to the Mishkaat DB.
- [ ] Daily encrypted backups (`mongodump | gpg`) with off-host rotation.
- [ ] Restore drill executed at least once.
- [ ] Verify TTL indexes exist:
  ```
  db.revoked_tokens.getIndexes()       // expects expires_at TTL
  db.login_attempts.getIndexes()       // expects last_seen TTL
  db.register_attempts.getIndexes()    // expects last_seen TTL
  ```

---

## 8. Reverse Proxy / TLS (Nginx)

- [ ] HTTPS enforced (Let's Encrypt or commercial cert); HTTP → 301 to HTTPS.
- [ ] Security headers:
  ```nginx
  add_header Strict-Transport-Security "max-age=63072000; includeSubDomains" always;
  add_header X-Frame-Options "DENY" always;
  add_header X-Content-Type-Options "nosniff" always;
  add_header Referrer-Policy "strict-origin-when-cross-origin" always;
  add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:;" always;
  add_header Permissions-Policy "geolocation=(), microphone=(), camera=()" always;
  ```
- [ ] `client_max_body_size` reduced (e.g., 2 MB).
- [ ] Optional edge rate-limit zone on `/api/auth/login` for belt-and-braces:
  ```nginx
  limit_req_zone $binary_remote_addr zone=mishkaat_login:10m rate=5r/m;
  location /api/auth/login { limit_req zone=mishkaat_login burst=3 nodelay; ... }
  ```
  (The server's MongoDB-backed limiter already handles multi-worker correctness, so this is defense-in-depth.)

---

## 9. Operational Monitoring

- [ ] `db.audit_logs` writes on every login attempt and on every center approval/rejection.
- [ ] Alert rule on repeated `LOGIN_FAILED` for a single IP within the lockout window.
- [ ] Alert rule on `PUBLIC_REGISTER_CENTER` floods.
- [ ] Weekly review of `GET /api/audit-logs` is on the calendar.
- [ ] `uvicorn.error` logs shipped to central store; retention ≥ 90 days.
- [ ] **Privacy regime acknowledged**: minor data is not exported to third-party analytics.

---

## 10. Patch Hygiene

- [ ] `pip audit` runs in CI; build fails on critical CVEs.
- [ ] `requirements.txt` is pinned (including the new `cryptography` dep).
- [ ] Quarterly Python and MongoDB minor-version review.

---

## 11. Sign-off

- [ ] Center name: ____________________________
- [ ] Onboarded by (admin name): _______________
- [ ] Date: _____________
- [ ] All boxes above checked or explicitly waived with justification logged in `audit_logs`.

> ⚠️ Do not deliver login credentials to a new center until **every** box in sections 1–6 is checked.
