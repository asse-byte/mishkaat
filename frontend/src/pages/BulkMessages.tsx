/*
English: This project is proprietary and confidential. All rights reserved to Abdoul Malick Cisse (Copyright © 2026).
Arabic: هذا المشروع ملكية خاصة وسري للغاية. جميع الحقوق محفوظة لـ عبد المالك سيسي (حقوق النشر © 2026).
*/
/**
 * المراسلات.
 *
 * [قرار المالك 2026-09-07] سلسلةُ المراسلة مغلقة: مديرُ النظام يخاطب مدراء
 * المراكز وحدهم، والمعلّم يخاطب مديرَ مركزه وحده، والمدير بينهما — ويُرسل
 * أيضاً إلى طلابه وأوليائهم.
 *
 * والجهاتُ التي يجوز لي مراسلتُها تُقرأ من الخادم (`/messages/audiences`) لا
 * تُخمَّن هنا: قائمةٌ مكتوبة في الواجهة تفترق عن قاعدة الخادم بأوّل تعديل،
 * فتعرض للمستخدم خياراً يُردّ بـ403 حين يضغطه.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { LoadingSpinner } from '@/components/ui/loading';
import {
  Send, MessageSquare, Inbox, Plus, CheckCircle2, Calendar,
  X, Paperclip, Trash2, Pencil, Download, FileText,
} from 'lucide-react';
import api from '@/services/api';
import PageHeader from '@/components/ui/PageHeader';
import { errorMessage } from '@/lib/errors';

interface Reply {
  teacher_id: string;
  teacher_name: string;
  sender_role?: string;
  content: string;
  timestamp: string;
}

interface Attachment {
  file_id: string;
  filename: string;
  content_type?: string;
  size?: number;
}

interface BulkMessage {
  id: string;
  recipient_role: string;
  subject: string;
  content: string;
  center_id: string;
  sender_id: string;
  sender_name?: string;
  sender_role?: string;
  sent_at: string;
  edited_at?: string | null;
  attachments?: Attachment[];
  replies: Reply[];
}

interface Audience { value: string; label: string }

const ROLE_LABEL: Record<string, string> = {
  all_teachers: 'معلّمو المركز',
  student: 'الطلاب',
  parent: 'أولياء الأمور',
  center_manager: 'مدراء المراكز',
  admin: 'إدارة النظام',
};

function fileSize(bytes?: number): string {
  if (!bytes) return '';
  if (bytes < 1024) return `${bytes} بايت`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} ك.ب`;
  return `${(bytes / 1024 / 1024).toFixed(1)} م.ب`;
}

export default function BulkMessages() {
  const { user } = useAuth();
  const [messages, setMessages] = useState<BulkMessage[]>([]);
  const [audiences, setAudiences] = useState<Audience[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [tab, setTab] = useState<'inbox' | 'outbox'>('inbox');

  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<BulkMessage | null>(null);
  const [form, setForm] = useState({ subject: '', content: '', recipient_role: '' });
  const [pending, setPending] = useState<Attachment[]>([]);
  const [selected, setSelected] = useState<BulkMessage | null>(null);
  const [replyContent, setReplyContent] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const fileRef = useRef<HTMLInputElement>(null);

  const canSend = audiences.length > 0;

  const loadMessages = useCallback(async () => {
    try {
      setLoading(true);
      setError('');
      const path = tab === 'outbox' ? '/messages/broadcasts' : '/messages/inbox';
      const resp = await api.get<BulkMessage[]>(path);
      setMessages(resp.data);
    } catch (err: unknown) {
      setError(errorMessage(err, 'تعذّر تحميل الرسائل.'));
    } finally {
      setLoading(false);
    }
  }, [tab]);

  useEffect(() => { loadMessages(); }, [loadMessages]);

  useEffect(() => {
    api.get<{ audiences: Audience[] }>('/messages/audiences')
      .then(r => {
        setAudiences(r.data.audiences || []);
        setForm(f => ({ ...f, recipient_role: r.data.audiences?.[0]?.value || '' }));
      })
      .catch(() => setAudiences([]));
  }, []);

  const attach = async (file: File) => {
    const body = new FormData();
    body.append('file', file);
    try {
      setSubmitting(true);
      setError('');
      const r = await api.post<Attachment>('/messages/attachments', body,
        { headers: { 'Content-Type': 'multipart/form-data' } });
      setPending(list => [...list, r.data]);
    } catch (err: unknown) {
      setError(errorMessage(err, 'تعذّر رفع الوثيقة'));
    } finally {
      setSubmitting(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  };

  const openCompose = () => {
    setEditing(null);
    setForm({ subject: '', content: '', recipient_role: audiences[0]?.value || '' });
    setPending([]);
    setError('');
    setShowForm(true);
  };

  const openEdit = (m: BulkMessage) => {
    setEditing(m);
    setForm({ subject: m.subject, content: m.content, recipient_role: m.recipient_role });
    setPending(m.attachments || []);
    setError('');
    setShowForm(true);
  };

  const submit = async () => {
    if (!form.subject.trim() || !form.content.trim()) {
      setError('اكتب عنوان الرسالة ونصّها');
      return;
    }
    try {
      setSubmitting(true);
      setError('');
      const payload = { ...form, attachments: pending };
      if (editing) {
        await api.put(`/messages/${editing.id}`, payload);
        setNotice('صُحّحت الرسالة.');
      } else {
        await api.post('/messages/broadcast', payload);
        setNotice('أُرسلت الرسالة.');
      }
      setShowForm(false);
      setEditing(null);
      setPending([]);
      setTab('outbox');
      await loadMessages();
    } catch (err: unknown) {
      setError(errorMessage(err, 'تعذّر إرسال الرسالة'));
    } finally {
      setSubmitting(false);
    }
  };

  const withdraw = async (m: BulkMessage) => {
    if (!window.confirm(`سحبُ رسالة «${m.subject}»؟ لن تعود تظهر لمن أُرسلت إليهم.`)) return;
    try {
      setSubmitting(true);
      await api.delete(`/messages/${m.id}`);
      setNotice('سُحبت الرسالة.');
      setSelected(null);
      await loadMessages();
    } catch (err: unknown) {
      setError(errorMessage(err, 'تعذّر سحب الرسالة'));
    } finally {
      setSubmitting(false);
    }
  };

  const sendReply = async () => {
    if (!selected || !replyContent.trim()) return;
    try {
      setSubmitting(true);
      setError('');
      const r = await api.post<BulkMessage>(`/messages/${selected.id}/reply`,
        { content: replyContent });
      setSelected(r.data);
      setReplyContent('');
      await loadMessages();
    } catch (err: unknown) {
      setError(errorMessage(err, 'تعذّر إرسال الردّ'));
    } finally {
      setSubmitting(false);
    }
  };

  const download = async (m: BulkMessage, att: Attachment) => {
    try {
      const r = await api.get(`/messages/${m.id}/attachments/${att.file_id}`,
        { responseType: 'blob' });
      const url = URL.createObjectURL(r.data as Blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = att.filename;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err: unknown) {
      setError(errorMessage(err, 'تعذّر تنزيل الوثيقة'));
    }
  };

  const attachmentRow = (m: BulkMessage) => (
    (m.attachments || []).length > 0 && (
      <div className="flex flex-wrap gap-2 mt-2">
        {(m.attachments || []).map(a => (
          <button key={a.file_id} onClick={() => download(m, a)}
            className="flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5
                       rounded-lg bg-[hsl(var(--muted))] hover:bg-[hsl(var(--border))]">
            <FileText className="w-3.5 h-3.5 shrink-0" />
            <span className="truncate max-w-[180px]">{a.filename}</span>
            <span className="text-[hsl(var(--muted-foreground))]">{fileSize(a.size)}</span>
            <Download className="w-3 h-3 shrink-0" />
          </button>
        ))}
      </div>
    )
  );

  if (loading) {
    return <div className="flex items-center justify-center h-64"><LoadingSpinner size="lg" /></div>;
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <PageHeader
        title="المراسلات"
        subtitle={
          user?.role === 'admin' || user?.role === 'super_admin'
            ? 'مع مدراء المراكز'
            : user?.role === 'teacher'
              ? 'مع مدير المركز'
              : 'مع إدارة النظام ومعلّمي المركز وطلابه'
        }
      >
        {canSend && (
          <button onClick={openCompose} className="btn-primary text-sm">
            <Plus className="w-4 h-4" /> رسالة جديدة
          </button>
        )}
      </PageHeader>

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

      <div className="flex gap-2">
        {([
          ['inbox', 'الواردة', Inbox],
          ['outbox', 'الصادرة', Send],
        ] as const).map(([key, label, Icon]) => (
          (key === 'inbox' || canSend) && (
            <button key={key} onClick={() => setTab(key)}
              className={`px-5 py-2.5 rounded-xl font-bold text-sm border-2 flex items-center
                          gap-2 transition-colors ${
                tab === key
                  ? 'border-[hsl(var(--primary))] bg-[hsl(var(--muted))] text-[hsl(var(--primary))]'
                  : 'border-[hsl(var(--border))]'}`}>
              <Icon className="w-4 h-4" /> {label}
            </button>
          )
        ))}
      </div>

      {messages.length === 0 ? (
        <div className="bg-white rounded-[var(--radius-lg)] border border-[hsl(var(--border))]
                        text-center py-16">
          <MessageSquare className="w-14 h-14 mx-auto mb-3 text-[hsl(var(--muted-foreground))] opacity-35" />
          <p className="text-[hsl(var(--muted-foreground))] font-semibold">
            {tab === 'inbox' ? 'لا رسائل واردة' : 'لم تُرسل رسائل بعد'}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {messages.map(m => (
            <div key={m.id}
              className="bg-white rounded-[var(--radius-lg)] border border-[hsl(var(--border))]
                         p-5 shadow-sm">
              <div className="flex items-start justify-between gap-3 flex-wrap">
                <div className="min-w-0 flex-1">
                  <h3 className="font-bold truncate">{m.subject}</h3>
                  <p className="text-xs text-[hsl(var(--muted-foreground))] mt-0.5
                                flex items-center gap-2 flex-wrap">
                    <span>
                      {tab === 'inbox'
                        ? `من: ${m.sender_name || '—'}`
                        : `إلى: ${ROLE_LABEL[m.recipient_role] || m.recipient_role}`}
                    </span>
                    <span className="flex items-center gap-1">
                      <Calendar className="w-3 h-3" />
                      {new Date(m.sent_at).toLocaleDateString('ar-EG')}
                    </span>
                    {m.edited_at && <span>· صُحّحت</span>}
                  </p>
                </div>
                <div className="flex items-center gap-1.5 shrink-0">
                  {m.replies.length > 0 && (
                    <span className="text-[11px] font-bold bg-[hsl(var(--muted))] px-2.5 py-1 rounded-full">
                      {m.replies.length} ردّ
                    </span>
                  )}
                  <button onClick={() => { setSelected(m); setReplyContent(''); }}
                    className="text-xs font-bold px-3 py-1.5 rounded-lg bg-[hsl(var(--muted))]">
                    فتح
                  </button>
                  {tab === 'outbox' && (
                    <>
                      <button onClick={() => openEdit(m)} title="تصحيح"
                        className="p-1.5 rounded-lg text-[hsl(var(--ink-3))] hover:bg-[hsl(var(--muted))]">
                        <Pencil className="w-4 h-4" />
                      </button>
                      <button onClick={() => withdraw(m)} title="سحب"
                        className="p-1.5 rounded-lg text-[hsl(var(--ink-3))] hover:text-red-600
                                   hover:bg-red-50">
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </>
                  )}
                </div>
              </div>
              <p className="text-sm mt-2 line-clamp-2 text-[hsl(var(--muted-foreground))]">
                {m.content}
              </p>
              {attachmentRow(m)}
            </div>
          ))}
        </div>
      )}

      {/* الإنشاء والتصحيح */}
      {showForm && (
        <div className="modal-overlay" onClick={() => setShowForm(false)}>
          <div className="bg-white rounded-[var(--radius-lg)] shadow-2xl w-full max-w-lg
                          max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
            <div className="gradient-primary p-5 rounded-t-3xl flex items-center
                            justify-between text-white sticky top-0 z-10">
              <h3 className="text-lg font-bold flex items-center gap-2">
                <Send className="w-5 h-5 text-[hsl(var(--gold))]" />
                {editing ? 'تصحيح الرسالة' : 'رسالة جديدة'}
              </h3>
              <button onClick={() => setShowForm(false)} className="text-white/80 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-5 space-y-4">
              {error && <div className="p-3 bg-red-50 text-red-600 rounded-xl text-xs">{error}</div>}

              <div>
                <label className="text-xs font-bold block mb-1">إلى *</label>
                <select value={form.recipient_role} disabled={!!editing}
                  onChange={e => setForm({ ...form, recipient_role: e.target.value })}
                  className="w-full h-11 px-3 rounded-xl border-2 border-[hsl(var(--border))]
                             text-sm bg-white disabled:opacity-60">
                  {audiences.map(a => (
                    <option key={a.value} value={a.value}>{a.label}</option>
                  ))}
                </select>
                {editing && (
                  <p className="text-[11px] text-[hsl(var(--muted-foreground))] mt-1">
                    الجهة المستقبِلة لا تُغيَّر بعد الإرسال — رسالةٌ قرأها قومٌ لا تُنقل إلى غيرهم.
                  </p>
                )}
              </div>

              <div>
                <label className="text-xs font-bold block mb-1">العنوان *</label>
                <input value={form.subject}
                  onChange={e => setForm({ ...form, subject: e.target.value })}
                  className="w-full h-11 px-3 rounded-xl border-2 border-[hsl(var(--border))] text-sm" />
              </div>

              <div>
                <label className="text-xs font-bold block mb-1">النصّ *</label>
                <textarea value={form.content}
                  onChange={e => setForm({ ...form, content: e.target.value })}
                  className="w-full p-3 rounded-xl border-2 border-[hsl(var(--border))]
                             text-sm min-h-[120px]" />
              </div>

              <div>
                <label className="text-xs font-bold block mb-2">الوثائق المرفقة</label>
                {pending.length > 0 && (
                  <div className="space-y-1.5 mb-2">
                    {pending.map(a => (
                      <div key={a.file_id}
                        className="flex items-center justify-between gap-2 text-xs
                                   bg-[hsl(var(--muted))] px-3 py-2 rounded-lg">
                        <span className="flex items-center gap-1.5 min-w-0">
                          <FileText className="w-3.5 h-3.5 shrink-0" />
                          <span className="truncate">{a.filename}</span>
                          <span className="text-[hsl(var(--muted-foreground))] shrink-0">
                            {fileSize(a.size)}
                          </span>
                        </span>
                        <button onClick={() => setPending(l => l.filter(x => x.file_id !== a.file_id))}
                          className="text-[hsl(var(--muted-foreground))] hover:text-red-600 shrink-0">
                          <X className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
                <button onClick={() => fileRef.current?.click()} disabled={submitting}
                  className="w-full border-2 border-dashed border-[hsl(var(--border))]
                             rounded-xl py-3 text-xs font-bold flex items-center
                             justify-center gap-2 disabled:opacity-60">
                  <Paperclip className="w-4 h-4" /> إرفاق وثيقة
                </button>
                <p className="text-[11px] text-[hsl(var(--muted-foreground))] mt-1.5">
                  PDF أو صورة، بحجم لا يتجاوز 5 ميغابايت للملفّ الواحد.
                </p>
                <input ref={fileRef} type="file" className="hidden"
                  accept="application/pdf,image/png,image/jpeg,image/webp"
                  onChange={e => { const f = e.target.files?.[0]; if (f) attach(f); }} />
              </div>

              <div className="flex gap-2 pt-3 border-t">
                <button onClick={submit} disabled={submitting}
                  className="flex-1 gradient-primary text-white font-bold py-3 rounded-xl text-sm">
                  {submitting ? 'جارٍ الإرسال...' : (editing ? 'حفظ التصحيح' : 'إرسال')}
                </button>
                <button onClick={() => setShowForm(false)}
                  className="px-5 py-3 border rounded-xl text-sm font-semibold">إلغاء</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* قراءة الرسالة والردّ */}
      {selected && (
        <div className="modal-overlay" onClick={() => setSelected(null)}>
          <div className="bg-white rounded-[var(--radius-lg)] shadow-2xl w-full max-w-lg
                          max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
            <div className="gradient-primary p-5 rounded-t-3xl flex items-center
                            justify-between text-white sticky top-0 z-10">
              <h3 className="text-lg font-bold truncate">{selected.subject}</h3>
              <button onClick={() => setSelected(null)} className="text-white/80 hover:text-white shrink-0">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-5 space-y-4">
              <p className="text-xs text-[hsl(var(--muted-foreground))]">
                من {selected.sender_name || '—'} ·{' '}
                {new Date(selected.sent_at).toLocaleString('ar-EG')}
              </p>
              <p className="text-sm whitespace-pre-wrap leading-relaxed">{selected.content}</p>
              {attachmentRow(selected)}

              {selected.replies.length > 0 && (
                <div className="border-t pt-3 space-y-2">
                  <h4 className="text-xs font-bold">الردود</h4>
                  {selected.replies.map((r, i) => (
                    <div key={i} className="bg-[hsl(var(--muted))] rounded-xl p-3">
                      <p className="text-xs font-bold">{r.teacher_name}</p>
                      <p className="text-sm mt-1 whitespace-pre-wrap">{r.content}</p>
                    </div>
                  ))}
                </div>
              )}

              {user?.role !== 'student' && user?.role !== 'parent' && (
                <div className="border-t pt-3 space-y-2">
                  <textarea value={replyContent} onChange={e => setReplyContent(e.target.value)}
                    placeholder="اكتب ردّك..."
                    className="w-full p-3 rounded-xl border-2 border-[hsl(var(--border))]
                               text-sm min-h-[80px]" />
                  <button onClick={sendReply} disabled={submitting || !replyContent.trim()}
                    className="gradient-primary text-white font-bold px-5 py-2.5 rounded-xl
                               text-sm disabled:opacity-60">
                    إرسال الردّ
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
