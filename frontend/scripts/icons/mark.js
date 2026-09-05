/**
 * علامة «المشكاة» — الكوّة التي فيها المصباح.
 *
 * الهندسة مبنية على قوس مدبَّب متساوي الأضلاع (two-centred arch): نصفا القوس
 * قوسان دائريان نصف قطر كلٍّ منهما ضِعف نصف عرض الفتحة، ومركزُ كلٍّ منهما هو
 * مَنبِت النصف الآخر. هذه هي طريقة رسم المحراب نفسها، لا تقريب بمنحنيات بيزيه.
 *
 *   نصف العرض w = 104، خطّ المنبت y = 290، مركز الكوّة x = 256
 *   ارتفاع الرأس = 290 − w·√3 = 110
 *
 * كل الإحداثيات داخل مربّع 512×512 ومحصورة في دائرة نصف قطرها ≈182 حول المركز،
 * أي داخل «المنطقة الآمنة» لأيقونات maskable (0.4×512 = 204.8) بلا تصغير.
 */

const NICHE_TOP = '#232D4B';
const NICHE_BOT = '#141B2E';
const BRASS_HI = '#FDE8BE';
const BRASS = '#EFAA43';
const BRASS_LO = '#D08C2A';
const ARCH = '#D9A254';

/** الأشكال وحدها، بلا أرضية — تُستعمل داخل كل نسخة. */
const artwork = `
  <g>
    <!-- جوف الكوّة: تجويف أغمق من الجدار يعطي عمقاً بلا خطوط زائدة -->
    <path d="M 152 386 L 152 290 A 208 208 0 0 1 256 110 A 208 208 0 0 1 360 290 L 360 386 Z"
          fill="url(#recess)"/>

    <!-- وهج المصباح: الضوء ينتشر ويتجاوز حافّة الكوّة قليلاً كما يفعل الضوء -->
    <circle cx="256" cy="278" r="186" fill="url(#glow)"/>

    <!-- الكوّة: قائمتان يعلوهما قوس مدبَّب -->
    <path d="M 152 386 L 152 290 A 208 208 0 0 1 256 110 A 208 208 0 0 1 360 290 L 360 386"
          fill="none" stroke="${ARCH}" stroke-width="21"
          stroke-linecap="round" stroke-linejoin="round"/>

    <!-- عتبة الكوّة -->
    <path d="M 138 386 L 374 386" fill="none" stroke="${ARCH}" stroke-width="21" stroke-linecap="round"/>

    <g transform="translate(0,-8)">
      <!-- سلسلة التعليق -->
      <path d="M 256 130 L 256 182" fill="none" stroke="${BRASS_LO}" stroke-width="10" stroke-linecap="round"/>

      <!-- قنديل المسجد: فوّهة مُتَّسِعة، خصر، جسم منتفخ، قاعدة.
           الظلّ الخارجي منحنى واحد مستمرّ: عند الخصر وعند أعرض نقطة يكون المماسّ
           رأسياً على الجانبين، فلا ينكسر الخطّ. الانكسار عند الخصر هو ما كان يجعل
           القنديل يُقرأ «قِمعاً فوق كرة» عند 48 بكسل، لا نِسَبُ الأجزاء.
           الحافّة العليا مقوَّسة قليلاً لا مقطوعة: القنديل مفتوح، لا مصمَت. -->
      <path d="M 216 180
               C 222 210, 234 224, 234 248
               C 234 268, 192 280, 192 300
               C 192 322, 210 344, 238 344
               C 248 350, 264 350, 274 344
               C 302 344, 320 322, 320 300
               C 320 280, 278 268, 278 248
               C 278 224, 290 210, 296 180
               C 288 190, 224 190, 216 180 Z"
            fill="url(#lamp)"/>

      <!-- قلب اللهب: المصباح مُوقَد، لا كتلة نحاسية -->
      <ellipse cx="256" cy="300" rx="52" ry="40" fill="url(#core)"/>

      <!-- لمعة على كتف القنديل: تفصيلة واحدة تكفي لإعطاء الحجم -->
      <path d="M 220 272 C 209 288, 209 306, 217 322"
            fill="none" stroke="${BRASS_HI}" stroke-width="8"
            stroke-linecap="round" opacity=".5"/>

      <!-- كُرة القاع -->
      <circle cx="256" cy="360" r="7" fill="${BRASS_LO}"/>
    </g>
  </g>`;

const defs = `
  <defs>
    <linearGradient id="field" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="${NICHE_TOP}"/>
      <stop offset="1" stop-color="${NICHE_BOT}"/>
    </linearGradient>
    <radialGradient id="glow" cx="50%" cy="50%" r="50%">
      <stop offset="0"   stop-color="${BRASS}" stop-opacity=".34"/>
      <stop offset=".45" stop-color="${BRASS}" stop-opacity=".12"/>
      <stop offset="1"   stop-color="${BRASS}" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="lamp" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0"   stop-color="${BRASS_HI}"/>
      <stop offset=".55" stop-color="${BRASS}"/>
      <stop offset="1"   stop-color="${BRASS_LO}"/>
    </linearGradient>
    <radialGradient id="core" cx="50%" cy="45%" r="50%">
      <stop offset="0"   stop-color="#FFF7E4" stop-opacity=".95"/>
      <stop offset=".55" stop-color="${BRASS_HI}" stop-opacity=".45"/>
      <stop offset="1"   stop-color="${BRASS_HI}" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="recess" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0"   stop-color="#0B101E" stop-opacity=".7"/>
      <stop offset="1"   stop-color="#0B101E" stop-opacity="0"/>
    </linearGradient>
  </defs>`;

const wrap = (inner) =>
  `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">${defs}${inner}</svg>`;

/** أرضية مربّعة بحواف مستديرة — لأيقونة «any» ولسطح المكتب. */
const rounded = () =>
  wrap(`<rect width="512" height="512" rx="104" fill="url(#field)"/>${artwork}`);

/** أرضية سابغة — لأيقونة maskable ولأيقونة iOS (النظام هو من يقصّ الحواف). */
const fullBleed = () =>
  wrap(`<rect width="512" height="512" fill="url(#field)"/>${artwork}`);

/** الأشكال وحدها بخلفية شفّافة — للاستعمال داخل الواجهة. */
const transparent = () => wrap(artwork);

module.exports = { rounded, fullBleed, transparent, artwork, defs, NICHE_BOT, NICHE_TOP };
