/** بطاقة معاينة الروابط (og:image) — 1200×630. */
const path = require('path');
const sharp = require('sharp');
const { transparent, defs } = require('./mark');

const OUT = process.argv[2];
if (!OUT) { console.error('usage: node og.js <public-dir>'); process.exit(1); }

const W = 1200, H = 630;

const field = `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2=".3" y2="1">
      <stop offset="0" stop-color="#26314F"/>
      <stop offset="1" stop-color="#111827"/>
    </linearGradient>
    <radialGradient id="halo" cx="50%" cy="50%" r="50%">
      <stop offset="0"   stop-color="#EFAA43" stop-opacity=".30"/>
      <stop offset=".5"  stop-color="#EFAA43" stop-opacity=".09"/>
      <stop offset="1"   stop-color="#EFAA43" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect width="${W}" height="${H}" fill="url(#bg)"/>
  <!-- الوهج خلف العلامة على اليمين (الاتجاه من اليمين إلى اليسار) -->
  <circle cx="900" cy="315" r="330" fill="url(#halo)"/>
  <!-- خيط ذهبي على الحافّة السفلى -->
  <rect x="0" y="${H - 6}" width="${W}" height="6" fill="#D9A254"/>
</svg>`;

/** نصّ مُشكَّل عربياً — Pango يتكفّل بالوصل والاتجاه. */
const text = (markup, font) =>
  sharp({ text: { text: markup, font, rgba: true, dpi: 72, align: 'right' } }).png().toBuffer();

(async () => {
  const markPng = await sharp(Buffer.from(transparent())).resize(400, 400).png().toBuffer();

  const title = await text('<span foreground="#F2C97D">المشكاة</span>', 'Segoe UI Bold 88');
  const sub   = await text('<span foreground="#D3D9E6">نظام إدارة دور القرآن الكريم</span>', 'Segoe UI 34');
  const feat  = await text('<span foreground="#98A2B8">الطلاب · الحلقات · التسميع · الحضور · المالية</span>', 'Segoe UI 27');

  const meta = async (b) => { const m = await sharp(b).metadata(); return { b, w: m.width, h: m.height }; };
  const T = await meta(title), S = await meta(sub), F = await meta(feat);

  // كل النصوص محاذاة لليمين على خطّ واحد؛ العلامة يمينها
  const RIGHT = 620;             // الحافّة اليمنى لكتلة النصّ
  const blockH = T.h + 26 + S.h + 22 + F.h;
  let y = Math.round((H - blockH) / 2);

  await sharp(Buffer.from(field))
    .composite([
      { input: markPng, left: 700, top: Math.round((H - 400) / 2) },
      { input: T.b, left: RIGHT - T.w, top: y },
      { input: S.b, left: RIGHT - S.w, top: (y += T.h + 26) },
      { input: F.b, left: RIGHT - F.w, top: (y += S.h + 22) },
    ])
    .png({ compressionLevel: 9 })
    .toFile(path.join(OUT, 'icons', 'og-image.png'));

  console.log(`icons/og-image.png  ${W}×${H}`);
})().catch(e => { console.error(e); process.exit(1); });
