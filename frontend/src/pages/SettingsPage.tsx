/**
 * الإعدادات.
 *
 * كانت هذه الصفحة كلُّها واجهةً بلا خلف: خمسةُ مفاتيح تُحرَّك فلا تُحفظ في
 * شيء، وزرُّ «حفظ التغييرات» يعرض «تم الحفظ» ولا يُرسل طلباً واحداً، ووعدان
 * بـ«قريباً» — أحدهما (الوضع الداكن) لميزةٍ تعمل تماماً في الشريط العلوي فوقها.
 *
 * فبقي فيها ما يعمل حقّاً وذهب ما سواه: المظهرُ الذي يُحفظ فعلاً، وهويّةُ
 * المركز التي تُرفع إلى الخادم. ومفتاحٌ لا يفعل شيئاً أسوأ من غيابه: غيابُه
 * نقصٌ يُرى، ووجودُه كذبٌ لا يُرى.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { Settings, Moon, Sun, Building2, Upload, Trash2, CheckCircle2, Image } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { useTheme } from '@/lib/theme';
import { errorMessage } from '@/lib/errors';
import api from '@/services/api';

interface CenterInfo { id: string; name: string; logo_file_id?: string | null }

export default function SettingsPage() {
  const { user } = useAuth();
  const { theme, set } = useTheme();
  const canBrand = user?.role === 'center_manager' || user?.role === 'admin'
    || user?.role === 'super_admin';

  const [center, setCenter] = useState<CenterInfo | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  /** يتغيّر بعد كل رفع ليُجبر المتصفّح على إعادة جلب الشعار بدل نسخته المخبَّأة */
  const [stamp, setStamp] = useState(() => Date.now());
  const fileRef = useRef<HTMLInputElement>(null);

  const loadCenter = useCallback(async () => {
    if (!canBrand) return;
    try {
      const r = await api.get<CenterInfo[]>('/centers');
      const mine = user?.center_id
        ? r.data.find(c => c.id === user.center_id) || null
        : r.data[0] || null;
      setCenter(mine);
    } catch {
      /* المركز اختياريّ هنا — بقيّة الصفحة تعمل بدونه */
    }
  }, [canBrand, user?.center_id]);

  useEffect(() => { loadCenter(); }, [loadCenter]);

  const uploadLogo = async (file: File) => {
    if (!center) return;
    const form = new FormData();
    form.append('file', file);
    try {
      setBusy(true);
      setError('');
      await api.post(`/centers/${center.id}/logo`, form,
        { headers: { 'Content-Type': 'multipart/form-data' } });
      setStamp(Date.now());
      setNotice('رُفع شعار المركز — سيظهر على الشهادات والفواتير.');
      await loadCenter();
    } catch (err: unknown) {
      setError(errorMessage(err, 'تعذّر رفع الشعار'));
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  };

  const removeLogo = async () => {
    if (!center) return;
    if (!window.confirm('إزالة شعار المركز؟ ستعود الوثائق إلى علامة النظام.')) return;
    try {
      setBusy(true);
      setError('');
      await api.delete(`/centers/${center.id}/logo`);
      setStamp(Date.now());
      setNotice('أُزيل الشعار.');
      await loadCenter();
    } catch (err: unknown) {
      setError(errorMessage(err, 'تعذّرت إزالة الشعار'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-6 animate-fade-in pb-10">
      <div className="flex items-center gap-4 bg-white rounded-[var(--radius)] p-6 shadow-sm border border-[hsl(var(--border))]">
        <div className="w-14 h-14 rounded-[var(--radius)] bg-[hsl(var(--muted))] flex items-center justify-center">
          <Settings className="w-7 h-7 text-[hsl(var(--primary))]" />
        </div>
        <div>
          <h1 className="text-2xl font-bold mb-1">الإعدادات</h1>
          <p className="text-[hsl(var(--muted-foreground))] text-sm">
            ما يُحفظ فعلاً — لا أكثر
          </p>
        </div>
      </div>

      {error && (
        <div className="p-3 rounded-xl bg-red-50 text-red-700 text-sm font-semibold border border-red-200">
          {error}
        </div>
      )}
      {notice && (
        <div className="p-3 rounded-xl bg-emerald-50 text-emerald-800 text-sm font-semibold
                        border border-emerald-200 flex items-center justify-between gap-3">
          <span className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 shrink-0" /> {notice}
          </span>
          <button onClick={() => setNotice('')} className="text-xs shrink-0">إخفاء</button>
        </div>
      )}

      {/* المظهر */}
      <section className="bg-white rounded-[var(--radius)] p-6 shadow-sm border border-[hsl(var(--border))]">
        <h2 className="text-lg font-bold mb-1">المظهر</h2>
        <p className="text-sm text-[hsl(var(--muted-foreground))] mb-4">
          يُحفظ على هذا الجهاز، وهو نفسه الذي يقلبه الزرّ في الشريط العلوي.
        </p>
        <div className="flex flex-wrap gap-3">
          {([
            { key: 'light' as const, label: 'وضع فاتح', Icon: Sun },
            { key: 'dark' as const, label: 'وضع داكن', Icon: Moon },
          ]).map(({ key, label, Icon }) => (
            <button key={key} onClick={() => set(key)}
              className={`flex items-center gap-2 px-5 py-3 rounded-xl border-2 font-semibold text-sm transition-all ${
                theme === key
                  ? 'border-[hsl(var(--primary))] bg-[hsl(var(--muted))] text-[hsl(var(--primary))]'
                  : 'border-[hsl(var(--border))] hover:border-[hsl(var(--primary))]'}`}>
              <Icon className="w-5 h-5" />
              {label}
            </button>
          ))}
        </div>
      </section>

      {/* هويّة المركز */}
      {canBrand && (
        <section className="bg-white rounded-[var(--radius)] p-6 shadow-sm border border-[hsl(var(--border))]">
          <h2 className="text-lg font-bold mb-1 flex items-center gap-2">
            <Building2 className="w-5 h-5 text-[hsl(var(--primary))]" />
            هويّة المركز
          </h2>
          <p className="text-sm text-[hsl(var(--muted-foreground))] mb-5">
            الشعار يظهر على الشهادات والفواتير وكل وثيقةٍ يُصدرها النظام باسم
            {center?.name ? ` «${center.name}»` : ' المركز'}.
          </p>

          {!center ? (
            <p className="text-sm text-[hsl(var(--muted-foreground))]">
              لا يوجد مركز مرتبط بحسابك.
            </p>
          ) : (
            <div className="flex flex-wrap items-center gap-5">
              <div className="w-28 h-28 rounded-[var(--radius)] border-2 border-dashed
                              border-[hsl(var(--border))] flex items-center justify-center
                              overflow-hidden bg-[hsl(var(--muted))] shrink-0">
                {center.logo_file_id ? (
                  <img src={`/api/centers/${center.id}/logo?v=${stamp}`}
                    alt={`شعار ${center.name}`} className="w-full h-full object-contain p-2" />
                ) : (
                  <Image className="w-8 h-8 text-[hsl(var(--muted-foreground))] opacity-50" />
                )}
              </div>

              <div className="space-y-2 min-w-0">
                <div className="flex flex-wrap gap-2">
                  <button onClick={() => fileRef.current?.click()} disabled={busy}
                    className="gradient-primary text-white font-bold px-5 py-2.5 rounded-xl
                               text-sm flex items-center gap-2 disabled:opacity-60">
                    <Upload className="w-4 h-4" />
                    {center.logo_file_id ? 'استبدال الشعار' : 'رفع الشعار'}
                  </button>
                  {center.logo_file_id && (
                    <button onClick={removeLogo} disabled={busy}
                      className="border-2 border-[hsl(var(--border))] font-bold px-4 py-2.5
                                 rounded-xl text-sm flex items-center gap-2 disabled:opacity-60">
                      <Trash2 className="w-4 h-4" /> إزالة
                    </button>
                  )}
                </div>
                <p className="text-xs text-[hsl(var(--muted-foreground))]">
                  PNG أو JPEG أو WEBP، بحجم لا يتجاوز 512 كيلوبايت.
                  ويُفضَّل شعارٌ بخلفيّة شفّافة ليظهر نظيفاً على ورق الشهادة.
                </p>
              </div>

              <input ref={fileRef} type="file" className="hidden"
                accept="image/png,image/jpeg,image/webp"
                onChange={e => {
                  const f = e.target.files?.[0];
                  if (f) uploadLogo(f);
                }} />
            </div>
          )}
        </section>
      )}

      {/* ما لا يُضبط من هنا — يُقال صراحةً بدل مفاتيح لا تعمل */}
      <section className="bg-white rounded-[var(--radius)] p-6 shadow-sm border border-[hsl(var(--border))]">
        <h2 className="text-lg font-bold mb-3">أمورٌ تُضبط من مكانٍ آخر</h2>
        <ul className="text-sm text-[hsl(var(--muted-foreground))] space-y-2 leading-relaxed">
          <li>• كلمة المرور واسمك وهاتفك: من <strong>الملف الشخصي</strong>.</li>
          <li>• حسابات الطلاب وأولياء الأمور: من ملفّ الطالب في صفحة <strong>الطلاب</strong>.</li>
          <li>• بيانات المركز واسمه وعنوانه: من صفحة <strong>المراكز</strong> لدى إدارة النظام.</li>
        </ul>
      </section>
    </div>
  );
}
