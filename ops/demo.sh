#!/usr/bin/env bash
# عرض تجريبي محلي للمشكاة برابط يمكن مشاركته — بلا رفع إلى خادم حقيقي.
#   ./ops/demo.sh            يشغّل كل شيء على http://localhost:3000
#   ./ops/demo.sh --tunnel   ويفتح رابطاً عاماً مؤقتاً (يحتاج cloudflared)
# قاعدة البيانات هنا منفصلة (quran_center_demo) ومعبّأة ببيانات تجريبية بكلمات مرور README المعروفة،
# فلا تستعمل هذا الوضع ببيانات حقيقية أبداً.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT=$PWD
TUNNEL=0; [ "${1:-}" = "--tunnel" ] && TUNNEL=1
PIDS=()
cleanup() { for p in "${PIDS[@]:-}"; do kill "$p" 2>/dev/null || true; done; [ -n "${MONGO_CID:-}" ] && docker rm -f "$MONGO_CID" >/dev/null 2>&1 || true; }
trap cleanup EXIT INT TERM

# 1) MongoDB: يُستعمل الموجود على 27017، وإلا تُشغَّل حاوية مؤقتة
if ! (echo > /dev/tcp/127.0.0.1/27017) 2>/dev/null; then
  command -v docker >/dev/null || { echo "لا MongoDB على 27017 ولا Docker. ثبّت أحدهما."; exit 1; }
  MONGO_CID=$(docker run -d --rm -p 27017:27017 mongo:7.0)
  echo "→ MongoDB (docker) $MONGO_CID"; sleep 4
fi

# 2) الخادم الخلفي (SEED_DEMO_DATA يُنشئ الحسابات التجريبية)
python3 -m venv .demo-venv 2>/dev/null || true
.demo-venv/bin/pip install -q -r backend/requirements.txt
(cd backend && DB_NAME=quran_center_demo SEED_DEMO_DATA=true APP_ENV=development \
  INITIAL_ADMIN_PASSWORD=admin123 INITIAL_SUPER_ADMIN_PASSWORD=superadmin123 \
  exec "$ROOT/.demo-venv/bin/uvicorn" server:app --host 127.0.0.1 --port 8001) &
PIDS+=($!)

# 3) الواجهة: بناء ثم معاينة (تمرّر /api إلى 8001 — أصل واحد، فلا حاجة لـ CORS)
(cd frontend && npm ci --silent && npm run build --silent && exec npx vite preview) &
PIDS+=($!)

sleep 8
echo; echo "✅ جاهز محلياً:   http://localhost:3000"
echo "   على نفس الشبكة:  http://$(hostname -I 2>/dev/null | awk '{print $1}'):3000"
echo "   الدخول: superadmin/superadmin123 · admin/admin123 · manager1/manager123 · teacher1/teacher123 · student1/student123 · parent1/parent123"

if [ $TUNNEL = 1 ]; then
  command -v cloudflared >/dev/null || { echo "ثبّت cloudflared: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/"; exit 1; }
  echo "→ الرابط العام سيظهر أدناه (trycloudflare.com):"
  cloudflared tunnel --url http://localhost:3000
else
  wait
fi
