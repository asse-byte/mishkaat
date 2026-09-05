// عامل الخدمة — المشكاة (PWA)
//
// اسم المخزن يحمل رقم إصدار: تغييره يُبطل كل ما خزّنه الإصدار السابق. رُفع إلى v3
// مع تغيير الأيقونات والبيان، وإلا لظلّت الأجهزة المثبَّتة تعرض الأيقونة الخضراء
// القديمة والاسم القديم إلى أن يُفرَّغ المخزن يدوياً.
const CACHE_NAME = 'mishkaat-v3';
const STATIC_ASSETS = [
  '/',
  '/manifest.json',
  '/favicon.svg',
  '/icons/icon-192x192.png',
  '/icons/icon-512x512.png',
  '/icons/maskable-192x192.png',
  '/icons/apple-touch-icon.png',
];

// التثبيت: تخزين الأصول الثابتة
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      // addAll ذرّي: فشل أصل واحد يُسقط التثبيت كلّه ويُبقي العامل القديم يعمل.
      // نُخزّن كلاً على حدة حتى لا يُعطّل ملفٌ مفقود التحديثَ بأسره.
      return Promise.all(
        STATIC_ASSETS.map((url) => cache.add(url).catch(() => undefined))
      );
    })
  );
  self.skipWaiting();
});

// التفعيل: تنظيف المخازن القديمة
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
      );
    })
  );
  self.clients.claim();
});

// الجلب: الشبكة أولاً ثم المخزن
self.addEventListener('fetch', (event) => {
  const { request } = event;

  if (request.method !== 'GET') return;
  if (!request.url.startsWith('http:') && !request.url.startsWith('https:')) return;
  // طلبات الـAPI تذهب إلى الشبكة دائماً — ولا تُخزَّن أبداً: بعضها يحمل بيانات
  // شخصية، وقناة الإشعارات (SSE) بثّ لا ينتهي فلا معنى لتخزينه.
  if (request.url.includes('/api/')) return;

  event.respondWith(
    fetch(request)
      .then((response) => {
        // لا يُخزَّن إلا ردٌّ كامل ناجح. الردّ الجزئي (206) يرفضه cache.put
        // برمي استثناء، وردّ الخطأ (404/500) لو خُزِّن لظلّ يُقدَّم بلا اتصال.
        if (response.ok && response.status === 200 && response.type !== 'opaque') {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(request, clone)).catch(() => {});
        }
        return response;
      })
      .catch(async () => {
        const cached = await caches.match(request);
        if (cached) return cached;
        // تطبيق صفحة واحدة: أي مسار تنقُّل يُخدَم بقشرة التطبيق نفسها
        if (request.mode === 'navigate') {
          const shell = await caches.match('/');
          if (shell) return shell;
        }
        return Response.error();
      })
  );
});
