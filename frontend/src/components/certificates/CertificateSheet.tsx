/**
 * ورقة الشهادة — تصميمٌ واحد لكل شهادات النظام.
 *
 * كانت شهادةُ المسابقة مرسومةً داخل صفحة المسابقات، فأيُّ شهادةٍ جديدة تعني
 * نسخَ مئة سطرٍ ثمّ افتراقَ النسختين. وهي الآن مكوّنٌ واحد تستدعيه المسابقات
 * والمحطّات معاً، فتتحسّن الشهادتان بتحسينٍ واحد.
 *
 * **الألوان قيمٌ ثابتة عن قصد، لا رموزَ النظام.** الشهادة تُطبع على ورقٍ أبيض
 * دائماً، ورموزُ النظام تنقلب في الوضع الليلي: من طبعها ليلاً كان يحصل على
 * نصٍّ فاتح على ورقٍ أبيض.
 *
 * **وشعار المركز هو الذي يتصدّرها لا شعار البرنامج.** الشهادة تُنسب إلى من
 * يمنحها: مركزُ التحفيظ. فإن لم يرفع المركز شعاره ظهرت علامةُ المشكاة بديلاً.
 */
import { useState } from 'react';
import { CornerFlourish, EightPointStar, OrnamentDivider, StarWatermark } from './Ornaments';
import MishkaatMark from '@/components/ui/MishkaatMark';

export interface Certificate {
  id: string;
  serial: string;
  kind: 'competition' | 'milestone';
  center_id: string;
  center_name?: string | null;
  student_name?: string | null;
  halaqah_name?: string | null;
  title: string;
  subtitle?: string | null;
  branch?: string | null;
  rank?: number | null;
  score?: number | null;
  judges_names?: string[];
  milestone?: string | null;
  pages_memorized?: number | null;
  issued_by_name?: string | null;
  issued_at: string;
}

// حبرٌ داكن، وذهبٌ نحاسيّ، ورمادٌ للهوامش — قيمٌ ثابتة تُطبع كما هي
const INK = '#151A24';
const NAVY = '#1B233C';
const BRASS = '#9C6F1C';
const MUTED = '#5B6474';
const RULE = '#D8DCE4';

const RANK_WORD: Record<number, string> = {
  1: 'المركز الأوّل', 2: 'المركز الثاني', 3: 'المركز الثالث',
};

function arabicDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString('ar-EG', {
      year: 'numeric', month: 'long', day: 'numeric',
    });
  } catch {
    return iso.slice(0, 10);
  }
}

export default function CertificateSheet({ cert }: { cert: Certificate }) {
  const isCompetition = cert.kind === 'competition';
  // المركز الذي لم يرفع شعاره تظهر عليه علامةُ المشكاة — بديلٌ لا تراكب
  const [logoOk, setLogoOk] = useState(true);

  return (
    <div className="relative w-full bg-white" dir="rtl"
      style={{ color: INK, aspectRatio: '297 / 210' }}>

      {/* الإطار المزدوج */}
      <div className="absolute inset-[10px] border-[3px]" style={{ borderColor: NAVY }} />
      <div className="absolute inset-[19px] border" style={{ borderColor: BRASS }} />

      {/* علامةٌ مائية خفيفة جداً — تُرى ولا تُزاحم النصّ */}
      <div className="absolute inset-[24px] overflow-hidden opacity-[0.07]"
        style={{ color: NAVY }}>
        <StarWatermark className="w-full h-full" />
      </div>

      {/* تفريعات الزوايا الأربع — مكوّنٌ واحد يُدار */}
      <div className="absolute top-[22px] right-[22px]" style={{ color: BRASS }}>
        <CornerFlourish className="w-14 h-14" />
      </div>
      <div className="absolute top-[22px] left-[22px] -scale-x-100" style={{ color: BRASS }}>
        <CornerFlourish className="w-14 h-14" />
      </div>
      <div className="absolute bottom-[22px] right-[22px] -scale-y-100" style={{ color: BRASS }}>
        <CornerFlourish className="w-14 h-14" />
      </div>
      <div className="absolute bottom-[22px] left-[22px] -scale-x-100 -scale-y-100"
        style={{ color: BRASS }}>
        <CornerFlourish className="w-14 h-14" />
      </div>

      <div className="relative h-full flex flex-col items-center justify-between
                      px-[10%] py-[5%] text-center">

        {/* الترويسة: البسملة، ثمّ شعار المركز واسمُه */}
        <div className="flex flex-col items-center gap-1">
          <p className="text-[9px] mb-1" style={{ color: MUTED }}>
            بسم الله الرحمن الرحيم
          </p>
          <div className="w-[68px] h-[68px] rounded-full border-2 flex items-center
                          justify-center overflow-hidden bg-white"
            style={{ borderColor: NAVY, color: BRASS }}>
            {cert.center_id && logoOk ? (
              <img src={`/api/centers/${cert.center_id}/logo`} alt=""
                className="w-full h-full object-contain p-1.5"
                onError={() => setLogoOk(false)} />
            ) : (
              <MishkaatMark className="w-9 h-9" />
            )}
          </div>
          <h2 className="text-[15px] font-extrabold mt-1.5" style={{ color: NAVY }}>
            {cert.center_name || 'مركز تحفيظ القرآن الكريم'}
          </h2>
        </div>

        {/* المتن */}
        <div className="flex flex-col items-center gap-2 max-w-[85%]">
          <div style={{ color: BRASS }}>
            <OrnamentDivider />
          </div>

          <h1 className="text-[30px] font-extrabold tracking-wide leading-none"
            style={{ color: NAVY, fontFamily: 'Georgia, "Amiri", serif' }}>
            {cert.title}
          </h1>

          <p className="text-[11px] font-medium leading-relaxed" style={{ color: MUTED }}>
            {isCompetition
              ? 'تُقدِّم إدارة المركز هذه الشهادة تقديراً وتكريماً للطالب'
              : 'تُقدِّم إدارة المركز هذه الشهادة تهنئةً وتكريماً للطالب'}
          </p>

          <div className="flex items-center gap-3" style={{ color: BRASS }}>
            <EightPointStar className="w-4 h-4" />
            <h2 className="text-[26px] font-extrabold px-3 pb-1 border-b-2"
              style={{ color: BRASS, borderColor: RULE }}>
              {cert.student_name || '—'}
            </h2>
            <EightPointStar className="w-4 h-4" />
          </div>

          <p className="text-[12px] leading-relaxed max-w-[92%]" style={{ color: INK }}>
            {isCompetition ? (
              <>
                لحصوله على <strong style={{ color: NAVY }}>
                  {cert.rank ? RANK_WORD[cert.rank] || `المركز ${cert.rank}` : 'مركزٍ متقدّم'}
                </strong>
                {cert.branch ? <> في فرع <strong style={{ color: NAVY }}>«{cert.branch}»</strong></> : null}
                {cert.subtitle ? <> من <strong>{cert.subtitle}</strong></> : null}
                {typeof cert.score === 'number'
                  ? <> بمجموع <strong style={{ color: NAVY }}>{cert.score}</strong> من 100</>
                  : null}
              </>
            ) : (
              <>
                بمناسبة <strong style={{ color: NAVY }}>{cert.subtitle}</strong>
                {cert.halaqah_name ? <>، في {cert.halaqah_name}</> : null}
                {typeof cert.pages_memorized === 'number'
                  ? <> بعد حفظٍ متقنٍ بلغ <strong style={{ color: NAVY }}>
                      {cert.pages_memorized}</strong> صفحة</>
                  : null}
              </>
            )}
            .
          </p>

          <p className="text-[10px] italic" style={{ color: MUTED }}>
            «خيرُكم مَن تعلَّم القرآنَ وعلَّمه»
          </p>

          <div style={{ color: BRASS }}>
            <OrnamentDivider />
          </div>
        </div>

        {/* التذييل: خانتا توقيعٍ تُوقَّعان باليد، ثمّ سطرُ التوثيق وحده.
            كان الرقمُ والتاريخ محشورين تحت خطّ التوقيع مباشرةً فيقرأهما
            القارئ كأنّهما جزءٌ من اسم الموقِّع. */}
        <div className="w-full">
          <div className="grid grid-cols-2 gap-16 px-[8%]">
            <div className="text-center">
              <span className="text-[9px] block mb-6" style={{ color: MUTED }}>
                {isCompetition ? 'رئيس لجنة التحكيم' : 'شيخ الحلقة'}
              </span>
              <div className="border-t pt-1" style={{ borderColor: RULE }}>
                <span className="text-[10px] font-bold">
                  {isCompetition ? (cert.judges_names?.[0] || '') : ''}
                </span>
                {!isCompetition && cert.halaqah_name && (
                  <span className="text-[8px] block" style={{ color: MUTED }}>
                    {cert.halaqah_name}
                  </span>
                )}
              </div>
            </div>
            <div className="text-center">
              <span className="text-[9px] block mb-6" style={{ color: MUTED }}>مدير المركز</span>
              <div className="border-t pt-1" style={{ borderColor: RULE }}>
                <span className="text-[10px] font-bold">{cert.issued_by_name || ''}</span>
              </div>
            </div>
          </div>

          <div className="flex items-center justify-center gap-4 mt-3 pt-2 text-[8px]
                          border-t" style={{ color: MUTED, borderColor: RULE }}>
            <span dir="ltr">{cert.serial}</span>
            <span>·</span>
            <span>حُرِّرت بتاريخ {arabicDate(cert.issued_at)}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
