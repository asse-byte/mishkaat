/** يولّد كل أيقونات المشكاة من العلامة المتّجهة الواحدة. */
const fs = require('fs');
const path = require('path');
const sharp = require('sharp');
const { rounded, fullBleed, transparent } = require('./mark');

const OUT = process.argv[2];
if (!OUT) { console.error('usage: node build.js <public-dir>'); process.exit(1); }
const ICONS = path.join(OUT, 'icons');
fs.mkdirSync(ICONS, { recursive: true });

const png = (svg, size, file) =>
  sharp(Buffer.from(svg))
    .resize(size, size)
    .png({ compressionLevel: 9, palette: false })
    .toFile(file)
    .then(() => console.log(`  ${path.relative(OUT, file).padEnd(34)} ${size}×${size}`));

/** حاوية ICO حول صورة PNG — الصيغة تسمح بذلك منذ ويندوز فيستا. */
function ico(pngBuf, size) {
  const header = Buffer.alloc(6);
  header.writeUInt16LE(0, 0);          // محجوز
  header.writeUInt16LE(1, 2);          // النوع: أيقونة
  header.writeUInt16LE(1, 4);          // عدد الصور
  const entry = Buffer.alloc(16);
  entry.writeUInt8(size === 256 ? 0 : size, 0);
  entry.writeUInt8(size === 256 ? 0 : size, 1);
  entry.writeUInt8(0, 2);              // لوحة ألوان: لا
  entry.writeUInt8(0, 3);
  entry.writeUInt16LE(1, 4);           // مستويات
  entry.writeUInt16LE(32, 6);          // بِتّات لكل بكسل
  entry.writeUInt32LE(pngBuf.length, 8);
  entry.writeUInt32LE(22, 12);         // الإزاحة
  return Buffer.concat([header, entry, pngBuf]);
}

(async () => {
  const svgRounded = rounded();
  const svgFull = fullBleed();
  const svgTransparent = transparent();

  console.log('العلامة المتّجهة:');
  fs.writeFileSync(path.join(ICONS, 'mishkaat.svg'), svgRounded);
  fs.writeFileSync(path.join(OUT, 'favicon.svg'), svgRounded);
  console.log('  icons/mishkaat.svg، favicon.svg');

  // أيقونات البيان — purpose: any (حوافّ مستديرة، لا يقصّها النظام)
  console.log('أيقونات any:');
  for (const s of [72, 96, 128, 144, 152, 192, 384, 512]) {
    await png(svgRounded, s, path.join(ICONS, `icon-${s}x${s}.png`));
  }

  // maskable — سابغة، والرسم داخل الدائرة الآمنة (0.8 من الضلع)
  console.log('أيقونات maskable:');
  for (const s of [192, 512]) {
    await png(svgFull, s, path.join(ICONS, `maskable-${s}x${s}.png`));
  }

  // iOS: 180×180، معتمة وسابغة — النظام يفرض قناعه الخاص
  console.log('iOS:');
  await png(svgFull, 180, path.join(ICONS, 'apple-touch-icon.png'));
  await png(svgFull, 180, path.join(OUT, 'apple-touch-icon.png')); // للطلب الافتراضي على الجذر

  // favicon
  console.log('favicon:');
  for (const s of [16, 32, 48]) {
    await png(svgRounded, s, path.join(ICONS, `favicon-${s}x${s}.png`));
  }
  const icoPng = await sharp(Buffer.from(svgRounded)).resize(32, 32).png().toBuffer();
  fs.writeFileSync(path.join(OUT, 'favicon.ico'), ico(icoPng, 32));
  console.log('  favicon.ico                        32×32');

  // نسخة شفّافة للاستعمال داخل الواجهة أو في التوثيق
  fs.writeFileSync(path.join(ICONS, 'mishkaat-mark.svg'), svgTransparent);
  console.log('  icons/mishkaat-mark.svg (شفّافة)');
})().catch(e => { console.error(e); process.exit(1); });
