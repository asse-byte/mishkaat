/*
English: This project is proprietary and confidential. All rights reserved to Abdoul Malick Cisse (Copyright © 2026).
Arabic: هذا المشروع ملكية خاصة وسري للغاية. جميع الحقوق محفوظة لـ عبد المالك سيسي (حقوق النشر © 2026).
*/
import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { LoadingSpinner } from '@/components/ui/loading';
import {
  Send, MessageSquare, Inbox, Users, ArrowLeftRight,
  Plus, CheckCircle2, AlertCircle, Calendar, Sparkles,
  ArrowUpRight, RefreshCw, X, Eye, ShieldAlert,
} from 'lucide-react';
import api from '@/services/api';
import PageHeader from '@/components/ui/PageHeader';

interface Reply {
  teacher_id: string;
  teacher_name: string;
  content: string;
  timestamp: string;
}

interface BulkMessage {
  id: string;
  recipient_role: string;
  subject: string;
  content: string;
  center_id: string;
  sender_id: string;
  sender_name?: string;
  sent_at: string;
  replies: Reply[];
}

export default function BulkMessages() {
  const { user } = useAuth();
  const [messages, setMessages] = useState<BulkMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  
  const [showBroadcastForm, setShowBroadcastForm] = useState(false);
  const [broadcastForm, setBroadcastForm] = useState({ 
    subject: '', 
    content: '', 
    recipient_role: user?.role === 'super_admin' ? 'center_manager' : 'all_teachers' 
  });
  const [selectedMessage, setSelectedMessage] = useState<BulkMessage | null>(null);
  const [replyContent, setReplyContent] = useState('');
  const [error, setError] = useState('');

  const isSuperAdmin = user?.role === 'super_admin';
  const isManager = user?.role === 'center_manager' || user?.role === 'admin';
  
  // Tab state: 'inbox' (received messages) or 'outbox' (sent broadcasts)
  const [activeTab, setActiveTab] = useState<'inbox' | 'outbox'>(
    isSuperAdmin ? 'outbox' : 'inbox'
  );

  const loadMessages = useCallback(async () => {
    try {
      setLoading(true);
      setError('');
      if (activeTab === 'outbox') {
        // Manager/SuperAdmin fetches sent broadcasts
        const resp = await api.get<BulkMessage[]>('/messages/broadcasts');
        setMessages(resp.data);
      } else {
        // Teacher/Manager fetches received inbox
        const resp = await api.get<BulkMessage[]>('/messages/inbox');
        setMessages(resp.data);
      }
    } catch {
      setError('حدث خطأ أثناء تحميل الرسائل.');
    } finally {
      setLoading(false);
    }
  }, [activeTab]);

  useEffect(() => {
    loadMessages();
    setSelectedMessage(null);
  }, [loadMessages]);

  const handleBroadcastSubmit = async () => {
    if (!broadcastForm.subject || !broadcastForm.content) {
      setError('الرجاء إدخال عنوان وبنية رسالة البث الجماعية');
      return;
    }
    try {
      setSubmitting(true);
      setError('');
      const resp = await api.post<BulkMessage>('/messages/broadcast', broadcastForm);
      setMessages(prev => [resp.data, ...prev]);
      setShowBroadcastForm(false);
      setBroadcastForm({ 
        subject: '', 
        content: '', 
        recipient_role: isSuperAdmin ? 'center_manager' : 'all_teachers' 
      });
    } catch (err: any) {
      setError(err.response?.data?.detail || 'فشل إرسال البث الجماعي');
    } finally {
      setSubmitting(false);
    }
  };

  const handleReplySubmit = async (messageId: string) => {
    if (!replyContent.trim()) return;
    try {
      setSubmitting(true);
      const resp = await api.post<BulkMessage>(`/messages/${messageId}/reply`, { content: replyContent });
      
      // Update locally
      setMessages(prev => prev.map(m => m.id === messageId ? resp.data : m));
      setSelectedMessage(resp.data);
      setReplyContent('');
    } catch (err: any) {
      alert(err.response?.data?.detail || 'فشل إرسال الرد');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <LoadingSpinner size="lg" />
    </div>
  );

  return (
    <div className="space-y-6 animate-fade-in text-[hsl(var(--foreground))]">
      
      {/* Header banner */}
      <PageHeader
        title="الرسائل الجماعية والبث المزدوج"
        subtitle={
          isSuperAdmin
            ? 'بث الرسائل التوجيهية العامة لجميع مدراء المراكز المعتمدة ومتابعة استجاباتهم'
            : activeTab === 'outbox'
              ? 'إرسال التوجيهات العامة لجميع المحفظين ومتابعة ردودهم في سلاسل نقاش تفاعلية'
              : 'استلام التوجيهات الرسمية والرد المباشر عليها'
        }
      />

      {/* Tabs Switcher for Center Manager (has both Inbox and Outbox) */}
      {isManager && (
        <div className="flex gap-2 p-1.5 bg-[hsl(var(--muted))]/40 rounded-[var(--radius)] w-fit">
          <button
            onClick={() => setActiveTab('inbox')}
            className={`px-5 py-2.5 rounded-xl text-xs font-bold transition-all flex items-center gap-2 ${
              activeTab === 'inbox' 
                ? 'bg-white text-[hsl(var(--primary))] shadow-sm' 
                : 'text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))]'
            }`}
          >
            <Inbox className="w-4 h-4" />
            الرسائل الواردة (من الإشراف العام)
          </button>
          <button
            onClick={() => setActiveTab('outbox')}
            className={`px-5 py-2.5 rounded-xl text-xs font-bold transition-all flex items-center gap-2 ${
              activeTab === 'outbox' 
                ? 'bg-white text-[hsl(var(--primary))] shadow-sm' 
                : 'text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))]'
            }`}
          >
            <Send className="w-4 h-4" />
            البث الصادر (للمحفظين والحلقات)
          </button>
        </div>
      )}

      {/* Action Bar */}
      <div className="flex justify-between items-center">
        <div className="flex items-center gap-2">
          <h3 className="font-bold text-base flex items-center gap-2">
            {activeTab === 'outbox' ? (
              <><Send className="w-5 h-5 text-[hsl(var(--primary))]" />إدارة رسائل البث الصادرة</>
            ) : (
              <><Inbox className="w-5 h-5 text-[hsl(var(--primary))]" />رسائل التوجيه الواردة</>
            )}
          </h3>
          <span className="badge-gold text-xs px-2.5 py-1 rounded-full font-bold">{messages.length} رسالة</span>
        </div>
        
        {(isSuperAdmin || (isManager && activeTab === 'outbox')) && (
          <button
            onClick={() => { setError(''); setShowBroadcastForm(true); }}
            className="gradient-primary text-white font-bold px-5 py-3 rounded-xl flex items-center gap-2 shadow-sm text-sm"
          >
            <Plus className="w-4.5 h-4.5" /> بث رسالة جديدة
          </button>
        )}
      </div>

      {/* Broadcast Create Modal */}
      {showBroadcastForm && (
        <div className="modal-overlay" onClick={() => setShowBroadcastForm(false)}>
          <div className="bg-white rounded-[var(--radius-lg)] shadow-2xl w-full max-w-lg" onClick={e => e.stopPropagation()}>
            <div className="gradient-primary p-5 rounded-t-3xl flex items-center justify-between text-white">
              <h3 className="text-lg font-bold flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-[hsl(var(--gold))]" /> بث إعلان وتوجيه رسمي جديد
              </h3>
              <button onClick={() => setShowBroadcastForm(false)} className="text-[hsl(var(--ink-3))] hover:text-white">✕</button>
            </div>
            <div className="p-5 space-y-4">
              {error && (
                <div className="p-3 bg-red-50 text-red-600 rounded-xl text-xs flex items-center gap-2">
                  <AlertCircle className="w-4 h-4" />{error}
                </div>
              )}
              <div>
                <label className="text-xs font-bold block mb-1">فئة المستلمين *</label>
                <select
                  value={broadcastForm.recipient_role}
                  onChange={e => setBroadcastForm({ ...broadcastForm, recipient_role: e.target.value })}
                  className="w-full h-11 px-3 rounded-xl border-2 border-[hsl(var(--border))] text-sm bg-white"
                >
                  {isSuperAdmin ? (
                    <option value="center_manager">جميع مدراء المراكز المعتمدة</option>
                  ) : (
                    <>
                      <option value="all_teachers">جميع معلمي الحلقات (المحفظين)</option>
                      <option value="student">جميع الطلاب</option>
                      <option value="parent">جميع أولياء الأمور</option>
                    </>
                  )}
                </select>
              </div>
              <div>
                <label className="text-xs font-bold block mb-1">عنوان الرسالة *</label>
                <input
                  placeholder="مثال: تنبيه بخصوص موعد المسابقة القرآنية السنوية"
                  value={broadcastForm.subject}
                  onChange={e => setBroadcastForm({ ...broadcastForm, subject: e.target.value })}
                  className="w-full h-11 px-3 rounded-xl border-2 border-[hsl(var(--border))] text-sm"
                />
              </div>
              <div>
                <label className="text-xs font-bold block mb-1">تفاصيل الرسالة ومحتواها *</label>
                <textarea
                  placeholder="اكتب التوجيهات العامة هنا بالتفصيل..."
                  value={broadcastForm.content}
                  onChange={e => setBroadcastForm({ ...broadcastForm, content: e.target.value })}
                  className="w-full p-3 rounded-xl border-2 border-[hsl(var(--border))] text-sm min-h-[120px]"
                />
              </div>
              <div className="flex gap-2 pt-3 border-t">
                <button onClick={handleBroadcastSubmit} disabled={submitting} className="flex-1 gradient-primary text-white font-bold py-3 rounded-xl text-sm">
                  {submitting ? 'جاري بث الرسالة...' : 'بث الإعلان الآن'}
                </button>
                <button onClick={() => setShowBroadcastForm(false)} className="px-5 py-3 border rounded-xl text-sm font-semibold">إلغاء</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Main Messaging Interface */}
      {messages.length === 0 ? (
        <div className="text-center py-20 bg-white rounded-[var(--radius-lg)] border-2 border-dashed border-[hsl(var(--border))]">
          <MessageSquare className="w-16 h-16 mx-auto mb-4 text-[hsl(var(--muted-foreground))] opacity-35" />
          <p className="text-[hsl(var(--muted-foreground))] font-semibold">لا توجد رسائل جماعية مرسلة أو واردة حالياً</p>
        </div>
      ) : (
        <div className="grid lg:grid-cols-3 gap-6">
          
          {/* Messages list (left 1/3) */}
          <div className="lg:col-span-1 space-y-3 max-h-[70vh] overflow-y-auto pr-1">
            {messages.map(msg => (
              <div
                key={msg.id}
                onClick={() => setSelectedMessage(msg)}
                className={`p-4 rounded-[var(--radius-lg)] border cursor-pointer transition-all stat-card flex flex-col justify-between ${
                  selectedMessage?.id === msg.id 
                    ? 'border-[hsl(var(--primary))] bg-[hsl(var(--primary-light))]/30 shadow-md' 
                    : 'bg-white border-[hsl(var(--border))]'
                }`}
              >
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-[10px] font-bold badge-gold text-white px-2 py-0.5 rounded-md">
                      بث: {msg.recipient_role === 'all_teachers' ? 'المحفظين' : msg.recipient_role === 'center_manager' ? 'مدراء المراكز' : msg.recipient_role}
                    </span>
                    <span className="text-[10px] text-[hsl(var(--muted-foreground))] flex items-center gap-1 font-mono">
                      <Calendar className="w-3 h-3 text-[hsl(var(--primary))]" />
                      {new Date(msg.sent_at).toLocaleDateString('ar-SA')}
                    </span>
                  </div>
                  <h4 className="font-bold text-sm text-[hsl(var(--foreground))] line-clamp-1">{msg.subject}</h4>
                  <p className="text-xs text-[hsl(var(--muted-foreground))] mt-1 line-clamp-2 leading-relaxed">{msg.content}</p>
                </div>
                <div className="flex items-center justify-between mt-3 pt-2.5 border-t border-[hsl(var(--border))]/50">
                  <span className="text-[10px] font-bold text-[hsl(var(--primary))]">
                    من: {msg.sender_name}
                  </span>
                  <span className="text-[10px] font-bold text-amber-600 bg-amber-50 border border-amber-100 px-2 py-0.5 rounded-lg flex items-center gap-1">
                    <MessageSquare className="w-3 h-3" />
                    {msg.replies.length} ردود
                  </span>
                </div>
              </div>
            ))}
          </div>

          {/* Selected message details & replies thread (right 2/3) */}
          <div className="lg:col-span-2 bg-white rounded-[var(--radius-lg)] border border-[hsl(var(--border))] shadow-sm flex flex-col justify-between min-h-[60vh] max-h-[70vh] overflow-hidden">
            {selectedMessage ? (
              <div className="flex flex-col h-full justify-between">
                
                {/* Scrollable details and thread */}
                <div className="p-6 overflow-y-auto space-y-6 flex-1 max-h-[50vh]">
                  
                  {/* Original Broadcast content */}
                  <div className="p-5 rounded-[var(--radius)] bg-[hsl(var(--muted))]/50 border-r-4 border-[hsl(var(--primary))]">
                    <div className="flex items-center justify-between mb-2">
                      <h3 className="font-bold text-base text-[hsl(var(--foreground))]">{selectedMessage.subject}</h3>
                      <span className="text-xs text-[hsl(var(--muted-foreground))] font-mono">
                        {new Date(selectedMessage.sent_at).toLocaleString('ar-SA')}
                      </span>
                    </div>
                    <p className="text-sm leading-relaxed text-[hsl(var(--muted-foreground))] whitespace-pre-wrap">{selectedMessage.content}</p>
                    <div className="mt-3 text-xs font-bold text-[hsl(var(--primary))]">
                      المرسل: {selectedMessage.sender_name}
                    </div>
                  </div>

                  {/* Threaded replies list */}
                  <div className="space-y-4">
                    <h4 className="font-bold text-sm text-[hsl(var(--foreground))] border-b pb-2 flex items-center gap-2">
                      <MessageSquare className="w-4 h-4 text-[hsl(var(--primary))]" />
                      الردود والمناقشات ({selectedMessage.replies.length})
                    </h4>
                    
                    {selectedMessage.replies.length === 0 ? (
                      <div className="text-center py-6 text-xs text-[hsl(var(--muted-foreground))]">
                        لا توجد ردود واردة على هذا البث بعد
                      </div>
                    ) : (
                      <div className="space-y-3 pl-2">
                        {selectedMessage.replies.map((reply, idx) => (
                          <div key={idx} className="p-3.5 rounded-[var(--radius)] bg-amber-50/40 border border-amber-100/50 flex flex-col gap-1 stat-card">
                            <div className="flex items-center justify-between text-xs mb-1">
                              <span className="font-bold text-[hsl(var(--primary))]">{reply.teacher_name}</span>
                              <span className="text-[10px] text-gray-400 font-mono">
                                {new Date(reply.timestamp).toLocaleString('ar-SA')}
                              </span>
                            </div>
                            <p className="text-xs text-[hsl(var(--foreground))] leading-relaxed">{reply.content}</p>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>

                {/* Reply typing input area (Only when viewing INBOX / receiving) */}
                {activeTab === 'inbox' && (
                  <div className="p-4 border-t border-[hsl(var(--border))] bg-[hsl(var(--muted))]/20 flex gap-2">
                    <input
                      placeholder="اكتب ردك أو استفسارك هنا..."
                      value={replyContent}
                      onChange={e => setReplyContent(e.target.value)}
                      onKeyDown={e => { if (e.key === 'Enter' && !submitting) handleReplySubmit(selectedMessage.id); }}
                      className="flex-1 h-11 px-4 rounded-xl border-2 border-[hsl(var(--border))] focus:outline-none focus:border-[hsl(var(--primary))] text-sm bg-white"
                    />
                    <button
                      onClick={() => handleReplySubmit(selectedMessage.id)}
                      disabled={submitting || !replyContent.trim()}
                      className="gradient-primary text-white h-11 px-5 rounded-xl font-bold flex items-center justify-center gap-1.5 transition-all text-xs disabled:opacity-50"
                    >
                      <Send className="w-4 h-4 rotate-180" /> إرسال الرد
                    </button>
                  </div>
                )}

              </div>
            ) : (
              <div className="flex flex-col items-center justify-center h-full text-center p-6 text-[hsl(var(--muted-foreground))]">
                <MessageSquare className="w-14 h-14 mb-3 text-[hsl(var(--muted-foreground))] opacity-30 animate-pulse" />
                <p className="font-bold text-sm">الرجاء اختيار رسالة من القائمة الجانبية لعرض سلسلة النقاش والردود المتبادلة</p>
              </div>
            )}
          </div>

        </div>
      )}

    </div>
  );
}
