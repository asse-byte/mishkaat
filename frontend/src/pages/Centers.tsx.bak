import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import {
  Building2, Plus, Search, Users, GraduationCap,
  BookOpen, Edit2, Trash2, X, CheckCircle2,
  AlertCircle, Phone, MapPin, Calendar, Eye,
} from 'lucide-react';
import api from '@/services/api';

interface CenterData {
  id: string;
  name: string;
  address?: string;
  phone?: string;
  manager_name?: string;
  manager_id?: string;
  is_active: boolean;
  created_at?: string;
  students_count: number;
  teachers_count: number;
  halaqat_count: number;
}

interface CenterDetail extends CenterData {
  teachers?: any[];
  manager_username?: string;
}

const emptyForm = {
  name: '', address: '', phone: '', email: '',
  manager_name: '', manager_username: '', manager_password: '', manager_email: '',
};

export default function Centers() {
  const { user } = useAuth();
  const [centers, setCenters]         = useState<CenterData[]>([]);
  const [search, setSearch]           = useState('');
  const [loading, setLoading]         = useState(true);
  const [showForm, setShowForm]       = useState(false);
  const [editCenter, setEditCenter]   = useState<CenterData | null>(null);
  const [detailCenter, setDetailCenter] = useState<CenterDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [formData, setFormData]       = useState(emptyForm);
  const [saving, setSaving]           = useState(false);
  const [error, setError]             = useState('');

  const loadCenters = useCallback(async () => {
    try {
      setLoading(true);
      const resp = await api.get('/centers');
      setCenters(resp.data || []);
    } catch { /* silent */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { loadCenters(); }, [loadCenters]);

  const openAdd = () => {
    setEditCenter(null);
    setFormData(emptyForm);
    setError('');
    setShowForm(true);
  };

  const openEdit = (c: CenterData) => {
    setEditCenter(c);
    setFormData({
      name: c.name, address: c.address || '', phone: c.phone || '',
      email: '', manager_name: c.manager_name || '',
      manager_username: '', manager_password: '', manager_email: '',
    });
    setError('');
    setShowForm(true);
  };

  const openDetail = async (c: CenterData) => {
    setDetailCenter(c);
    setDetailLoading(true);
    try {
      const resp = await api.get(`/centers/${c.id}/details`);
      setDetailCenter(resp.data);
    } catch {
      setDetailCenter(c);
    } finally { setDetailLoading(false); }
  };

  const handleSave = async () => {
    if (!formData.name.trim()) { setError('Ø§Ø³Ù… Ø§Ù„Ù…Ø±ÙƒØ² Ù…Ø·Ù„ÙˆØ¨'); return; }
    if (!editCenter && !formData.manager_username) { setError('Ø§Ø³Ù… Ù…Ø³ØªØ®Ø¯Ù… Ù…Ø¯ÙŠØ± Ø§Ù„Ù…Ø±ÙƒØ² Ù…Ø·Ù„ÙˆØ¨'); return; }
    if (!editCenter && !formData.manager_password) { setError('ÙƒÙ„Ù…Ø© Ù…Ø±ÙˆØ± Ù…Ø¯ÙŠØ± Ø§Ù„Ù…Ø±ÙƒØ² Ù…Ø·Ù„ÙˆØ¨Ø©'); return; }

    try {
      setSaving(true); setError('');
      if (editCenter) {
        await api.put(`/centers/${editCenter.id}`, {
          name: formData.name,
          address: formData.address,
          phone: formData.phone,
          manager_name: formData.manager_name || undefined,
        });
      } else {
        await api.post('/centers', {
          name: formData.name,
          address: formData.address,
          phone: formData.phone,
          manager_name: formData.manager_name,
          manager_username: formData.manager_username,
          manager_password: formData.manager_password,
          manager_email: formData.manager_email || undefined,
        });
      }
      setShowForm(false);
      await loadCenters();
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Ø­Ø¯Ø« Ø®Ø·Ø£ Ø£Ø«Ù†Ø§Ø¡ Ø§Ù„Ø­ÙØ¸');
    } finally { setSaving(false); }
  };

  const handleDelete = async (c: CenterData) => {
    if (!confirm(`Ù‡Ù„ Ø£Ù†Øª Ù…ØªØ£ÙƒØ¯ Ù…Ù† Ø­Ø°Ù Ù…Ø±ÙƒØ² "${c.name}"ØŸ`)) return;
    try {
      await api.delete(`/centers/${c.id}`);
      await loadCenters();
    } catch (e: any) {
      alert(e.response?.data?.detail || 'ÙØ´Ù„ Ø§Ù„Ø­Ø°Ù');
    }
  };

  const filtered = centers.filter(c =>
    c.name.includes(search) ||
    (c.manager_name || '').includes(search) ||
    (c.phone || '').includes(search)
  );

  return (
    <div className="space-y-6 animate-fade-in">

      {/* Header */}
      <div className="relative overflow-hidden rounded-3xl p-6 text-white shadow-xl gradient-primary">
        <div className="absolute top-[-30px] left-[-30px] w-40 h-40 rounded-full bg-white/5" />
        <div className="relative z-10 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-black mb-1">Ø¥Ø¯Ø§Ø±Ø© Ø§Ù„Ù…Ø±Ø§ÙƒØ²</h1>
            <p className="text-white/70 text-sm">{centers.length} Ù…Ø±ÙƒØ² Ù…Ø³Ø¬ÙŽÙ‘Ù„ ÙÙŠ Ø§Ù„Ù†Ø¸Ø§Ù…</p>
          </div>
          {user?.role === 'admin' && (
            <button onClick={openAdd}
              className="flex items-center gap-2 bg-white/20 hover:bg-white/30 text-white font-bold px-4 py-2.5 rounded-xl transition-all text-sm">
              <Plus className="w-4 h-4" /> Ø¥Ø¶Ø§ÙØ© Ù…Ø±ÙƒØ²
            </button>
          )}
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4 stagger">
        {[
          { label: 'Ø§Ù„Ù…Ø±Ø§ÙƒØ² Ø§Ù„Ù†Ø´Ø·Ø©', value: centers.filter(c => c.is_active).length, icon: Building2, cls: 'gradient-primary' },
          { label: 'Ø¥Ø¬Ù…Ø§Ù„ÙŠ Ø§Ù„Ù…Ø­ÙØ¸ÙŠÙ†', value: centers.reduce((s, c) => s + (c.teachers_count || 0), 0), icon: GraduationCap, cls: 'gradient-gold' },
          { label: 'Ø¥Ø¬Ù…Ø§Ù„ÙŠ Ø§Ù„Ø·Ù„Ø§Ø¨', value: centers.reduce((s, c) => s + (c.students_count || 0), 0), icon: Users, cls: 'stat-card-teal' },
        ].map(s => (
          <div key={s.label} className={`stat-card rounded-2xl p-5 text-white ${s.cls} shadow-lg`}>
            <div className="w-10 h-10 bg-white/20 rounded-xl flex items-center justify-center mb-3">
              <s.icon className="w-5 h-5 text-white" />
            </div>
            <p className="text-3xl font-black">{s.value}</p>
            <p className="text-white/70 text-sm mt-1">{s.label}</p>
          </div>
        ))}
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="absolute right-3 top-3.5 w-5 h-5 text-[hsl(var(--muted-foreground))]" />
        <input value={search} onChange={e => setSearch(e.target.value)}
          placeholder="Ø¨Ø­Ø« Ø¨Ø§Ù„Ø§Ø³Ù… Ø£Ùˆ Ù…Ø¯ÙŠØ± Ø§Ù„Ù…Ø±ÙƒØ² Ø£Ùˆ Ø§Ù„Ù‡Ø§ØªÙ..."
          className="form-input pr-10" />
      </div>

      {/* Centers Grid */}
      {loading ? (
        <div className="flex items-center justify-center h-40">
          <div className="w-10 h-10 border-4 border-[hsl(var(--primary))] border-t-transparent rounded-full animate-spin" />
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-16 text-[hsl(var(--muted-foreground))] bg-white rounded-3xl border-2 border-dashed border-[hsl(var(--border))]">
          <Building2 className="w-14 h-14 mx-auto mb-3 opacity-30" />
          <p className="font-medium">Ù„Ø§ ØªÙˆØ¬Ø¯ Ù…Ø±Ø§ÙƒØ²{search ? ' Ù…Ø·Ø§Ø¨Ù‚Ø© Ù„Ù„Ø¨Ø­Ø«' : ' Ù…Ø³Ø¬ÙŽÙ‘Ù„Ø©'}</p>
          {!search && user?.role === 'admin' && (
            <button onClick={openAdd} className="mt-3 text-[hsl(var(--primary))] font-bold text-sm underline">
              Ø¥Ø¶Ø§ÙØ© Ø£ÙˆÙ„ Ù…Ø±ÙƒØ²
            </button>
          )}
        </div>
      ) : (
        <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-5 stagger">
          {filtered.map(center => (
            <div key={center.id} className="bg-white rounded-3xl shadow-sm border border-[hsl(var(--border))] overflow-hidden stat-card">
              {/* Card header */}
              <div className="gradient-primary p-5">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <h3 className="text-lg font-black text-white truncate">{center.name}</h3>
                    {center.manager_name && (
                      <p className="text-white/70 text-sm mt-0.5 truncate">Ù…. {center.manager_name}</p>
                    )}
                  </div>
                  <span className={`text-[10px] font-bold px-2.5 py-1 rounded-full shrink-0 ${center.is_active ? 'bg-emerald-400/30 text-white' : 'bg-red-400/30 text-white'}`}>
                    {center.is_active ? 'Ù†Ø´Ø·' : 'Ù…ÙˆÙ‚ÙˆÙ'}
                  </span>
                </div>
              </div>

              {/* Stats row */}
              <div className="grid grid-cols-3 divide-x divide-x-reverse divide-[hsl(var(--border))] border-b border-[hsl(var(--border))]">
                {[
                  { icon: Users, val: center.students_count, label: 'Ø·Ø§Ù„Ø¨' },
                  { icon: GraduationCap, val: center.teachers_count, label: 'Ù…Ø­ÙØ¸' },
                  { icon: BookOpen, val: center.halaqat_count, label: 'Ø­Ù„Ù‚Ø©' },
                ].map(s => (
                  <div key={s.label} className="p-3 text-center">
                    <s.icon className="w-4 h-4 mx-auto mb-1 text-[hsl(var(--primary))]" />
                    <p className="font-black text-[hsl(var(--foreground))] text-base">{s.val || 0}</p>
                    <p className="text-xs text-[hsl(var(--muted-foreground))]">{s.label}</p>
                  </div>
                ))}
              </div>

              {/* Info */}
              <div className="p-4 space-y-2">
                {center.address && (
                  <div className="flex items-center gap-2 text-xs text-[hsl(var(--muted-foreground))]">
                    <MapPin className="w-3.5 h-3.5 shrink-0" />
                    <span className="truncate">{center.address}</span>
                  </div>
                )}
                {center.phone && (
                  <div className="flex items-center gap-2 text-xs text-[hsl(var(--muted-foreground))]" dir="ltr">
                    <Phone className="w-3.5 h-3.5 shrink-0" />
                    <span>{center.phone}</span>
                  </div>
                )}
                {center.created_at && (
                  <div className="flex items-center gap-2 text-xs text-[hsl(var(--muted-foreground))]">
                    <Calendar className="w-3.5 h-3.5 shrink-0" />
                    <span>ØªÙØ£Ø³Ø³: {new Date(center.created_at).toLocaleDateString('ar-SA')}</span>
                  </div>
                )}
              </div>

              {/* Actions */}
              {user?.role === 'admin' && (
                <div className="px-4 pb-4 flex gap-2">
                  <button onClick={() => openDetail(center)}
                    className="flex-1 flex items-center justify-center gap-1.5 text-xs font-bold py-2.5 rounded-xl gradient-primary text-white hover:opacity-90 transition-all">
                    <Eye className="w-3.5 h-3.5" /> Ø¹Ø±Ø¶ Ø§Ù„ØªÙØ§ØµÙŠÙ„
                  </button>
                  <button onClick={() => openEdit(center)}
                    title="ØªØ¹Ø¯ÙŠÙ„"
                    className="p-2.5 rounded-xl bg-[hsl(var(--gold-light))] text-[hsl(var(--gold-dark))] hover:opacity-80 transition-all">
                    <Edit2 className="w-4 h-4" />
                  </button>
                  <button onClick={() => handleDelete(center)}
                    title="Ø­Ø°Ù"
                    className="p-2.5 rounded-xl bg-red-50 text-red-600 hover:opacity-80 transition-all">
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Add/Edit Modal */}
      {showForm && (
        <div className="modal-overlay animate-fade-in">
          <div className="bg-white rounded-3xl shadow-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <div className="gradient-primary p-6 rounded-t-3xl flex items-center justify-between">
              <h2 className="text-lg font-black text-white">
                {editCenter ? 'ØªØ¹Ø¯ÙŠÙ„ Ø¨ÙŠØ§Ù†Ø§Øª Ø§Ù„Ù…Ø±ÙƒØ²' : 'Ø¥Ø¶Ø§ÙØ© Ù…Ø±ÙƒØ² Ø¬Ø¯ÙŠØ¯'}
              </h2>
              <button onClick={() => setShowForm(false)} className="p-2 rounded-xl bg-white/20 text-white hover:bg-white/30 transition-all">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-6 space-y-4">
              {/* Center Info */}
              <p className="text-xs font-bold text-[hsl(var(--primary))] uppercase tracking-wider">Ø¨ÙŠØ§Ù†Ø§Øª Ø§Ù„Ù…Ø±ÙƒØ²</p>
              <div>
                <label className="block text-sm font-bold text-[hsl(var(--foreground))] mb-1.5">Ø§Ø³Ù… Ø§Ù„Ù…Ø±ÙƒØ² *</label>
                <input className="form-input" placeholder="Ù…Ø«Ø§Ù„: Ù…Ø±ÙƒØ² Ø§Ù„Ù†ÙˆØ± Ù„ØªØ­ÙÙŠØ¸ Ø§Ù„Ù‚Ø±Ø¢Ù†"
                  value={formData.name} onChange={e => setFormData({ ...formData, name: e.target.value })} />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-bold text-[hsl(var(--foreground))] mb-1.5">Ø±Ù‚Ù… Ø§Ù„Ù‡Ø§ØªÙ</label>
                  <input className="form-input" placeholder="+222 XX XX XX XX" dir="ltr"
                    value={formData.phone} onChange={e => setFormData({ ...formData, phone: e.target.value })} />
                </div>
                <div>
                  <label className="block text-sm font-bold text-[hsl(var(--foreground))] mb-1.5">Ø§Ù„Ø¹Ù†ÙˆØ§Ù†</label>
                  <input className="form-input" placeholder="Ø­ÙŠ/Ù…Ù†Ø·Ù‚Ø©..."
                    value={formData.address} onChange={e => setFormData({ ...formData, address: e.target.value })} />
                </div>
              </div>

              {/* Manager Info - Only when adding */}
              {!editCenter && (
                <>
                  <hr className="border-[hsl(var(--border))]" />
                  <p className="text-xs font-bold text-[hsl(var(--primary))] uppercase tracking-wider">Ø­Ø³Ø§Ø¨ Ù…Ø¯ÙŠØ± Ø§Ù„Ù…Ø±ÙƒØ²</p>
                  <div>
                    <label className="block text-sm font-bold text-[hsl(var(--foreground))] mb-1.5">Ø§Ù„Ø§Ø³Ù… Ø§Ù„ÙƒØ§Ù…Ù„</label>
                    <input className="form-input" placeholder="Ø§Ø³Ù… Ù…Ø¯ÙŠØ± Ø§Ù„Ù…Ø±ÙƒØ²"
                      value={formData.manager_name} onChange={e => setFormData({ ...formData, manager_name: e.target.value })} />
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-sm font-bold text-[hsl(var(--foreground))] mb-1.5">Ø§Ø³Ù… Ø§Ù„Ù…Ø³ØªØ®Ø¯Ù… *</label>
                      <input className="form-input" placeholder="manager_nour" dir="ltr"
                        value={formData.manager_username} onChange={e => setFormData({ ...formData, manager_username: e.target.value })} />
                    </div>
                    <div>
                      <label className="block text-sm font-bold text-[hsl(var(--foreground))] mb-1.5">ÙƒÙ„Ù…Ø© Ø§Ù„Ù…Ø±ÙˆØ± *</label>
                      <input className="form-input" type="password" placeholder="â€¢â€¢â€¢â€¢â€¢â€¢â€¢â€¢" dir="ltr"
                        value={formData.manager_password} onChange={e => setFormData({ ...formData, manager_password: e.target.value })} />
                    </div>
                  </div>
                  <div>
                    <label className="block text-sm font-bold text-[hsl(var(--foreground))] mb-1.5">Ø§Ù„Ø¨Ø±ÙŠØ¯ Ø§Ù„Ø¥Ù„ÙƒØªØ±ÙˆÙ†ÙŠ</label>
                    <input className="form-input" type="email" placeholder="manager@center.com" dir="ltr"
                      value={formData.manager_email} onChange={e => setFormData({ ...formData, manager_email: e.target.value })} />
                  </div>
                </>
              )}

              {/* Edit manager name */}
              {editCenter && (
                <div>
                  <label className="block text-sm font-bold text-[hsl(var(--foreground))] mb-1.5">Ø§Ø³Ù… Ù…Ø¯ÙŠØ± Ø§Ù„Ù…Ø±ÙƒØ²</label>
                  <input className="form-input" placeholder="Ø§Ø³Ù… Ø§Ù„Ù…Ø¯ÙŠØ±"
                    value={formData.manager_name} onChange={e => setFormData({ ...formData, manager_name: e.target.value })} />
                </div>
              )}

              {error && (
                <div className="p-3 rounded-xl bg-red-50 text-red-700 text-sm flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 shrink-0" />{error}
                </div>
              )}

              <div className="flex gap-3 pt-2">
                <button onClick={handleSave} disabled={saving}
                  className="flex-1 gradient-primary text-white font-bold py-3 rounded-xl hover:opacity-90 transition-all disabled:opacity-60 flex items-center justify-center gap-2">
                  {saving
                    ? <span className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    : <><CheckCircle2 className="w-5 h-5" />{editCenter ? 'Ø­ÙØ¸ Ø§Ù„ØªØ¹Ø¯ÙŠÙ„Ø§Øª' : 'Ø¥Ù†Ø´Ø§Ø¡ Ø§Ù„Ù…Ø±ÙƒØ²'}</>}
                </button>
                <button onClick={() => setShowForm(false)}
                  className="px-5 py-3 rounded-xl border-2 border-[hsl(var(--border))] text-[hsl(var(--foreground))] font-bold hover:bg-[hsl(var(--muted))] transition-all">
                  Ø¥Ù„ØºØ§Ø¡
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Detail Modal */}
      {detailCenter && (
        <div className="modal-overlay animate-fade-in">
          <div className="bg-white rounded-3xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <div className="gradient-primary p-6 rounded-t-3xl flex items-center justify-between">
              <div>
                <h2 className="text-xl font-black text-white">{detailCenter.name}</h2>
                <p className="text-white/70 text-sm">ØªÙØ§ØµÙŠÙ„ Ø§Ù„Ù…Ø±ÙƒØ² Ø§Ù„ÙƒØ§Ù…Ù„Ø©</p>
              </div>
              <button onClick={() => setDetailCenter(null)} className="p-2 rounded-xl bg-white/20 text-white hover:bg-white/30 transition-all">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-6 space-y-5">
              {detailLoading ? (
                <div className="flex items-center justify-center h-32">
                  <div className="w-10 h-10 border-4 border-[hsl(var(--primary))] border-t-transparent rounded-full animate-spin" />
                </div>
              ) : (
                <>
                  {/* Basic Info */}
                  <div className="grid grid-cols-3 gap-4">
                    {[
                      { label: 'Ø§Ù„Ø·Ù„Ø§Ø¨', val: detailCenter.students_count || 0, icon: Users, cls: 'gradient-primary' },
                      { label: 'Ø§Ù„Ù…Ø­ÙØ¸ÙˆÙ†', val: detailCenter.teachers_count || 0, icon: GraduationCap, cls: 'gradient-gold' },
                      { label: 'Ø§Ù„Ø­Ù„Ù‚Ø§Øª', val: detailCenter.halaqat_count || 0, icon: BookOpen, cls: 'stat-card-teal' },
                    ].map(s => (
                      <div key={s.label} className={`${s.cls} rounded-2xl p-4 text-white text-center shadow-md`}>
                        <s.icon className="w-6 h-6 mx-auto mb-2" />
                        <p className="text-2xl font-black">{s.val}</p>
                        <p className="text-white/70 text-xs">{s.label}</p>
                      </div>
                    ))}
                  </div>

                  {/* Details */}
                  <div className="bg-[hsl(var(--muted))] rounded-2xl p-4 space-y-3">
                    <h4 className="font-black text-[hsl(var(--foreground))] text-sm">Ù…Ø¹Ù„ÙˆÙ…Ø§Øª Ø§Ù„ØªØ³Ø¬ÙŠÙ„</h4>
                    {[
                      { label: 'Ø§Ù„Ù…Ø¯ÙŠØ±', val: detailCenter.manager_name },
                      { label: 'Ø§Ù„Ù‡Ø§ØªÙ', val: detailCenter.phone, dir: 'ltr' },
                      { label: 'Ø§Ù„Ø¹Ù†ÙˆØ§Ù†', val: detailCenter.address },
                      { label: 'ØªØ§Ø±ÙŠØ® Ø§Ù„Ø¥Ù†Ø´Ø§Ø¡', val: detailCenter.created_at ? new Date(detailCenter.created_at).toLocaleDateString('ar-SA') : 'â€”' },
                      { label: 'Ø§Ù„Ø­Ø§Ù„Ø©', val: detailCenter.is_active ? 'Ù†Ø´Ø· âœ…' : 'Ù…ÙˆÙ‚ÙˆÙ â›”' },
                    ].map(row => row.val && (
                      <div key={row.label} className="flex items-center justify-between text-sm">
                        <span className="text-[hsl(var(--muted-foreground))] font-medium">{row.label}</span>
                        <span className="font-bold text-[hsl(var(--foreground))]" dir={row.dir as any}>{row.val}</span>
                      </div>
                    ))}
                  </div>

                  {/* Teachers list */}
                  {(detailCenter as any).teachers && (detailCenter as any).teachers.length > 0 && (
                    <div>
                      <h4 className="font-black text-[hsl(var(--foreground))] mb-3 flex items-center gap-2">
                        <GraduationCap className="w-4 h-4 text-[hsl(var(--primary))]" />
                        Ø§Ù„Ù…Ø­ÙØ¸ÙˆÙ† ({(detailCenter as any).teachers.length})
                      </h4>
                      <div className="space-y-2">
                        {(detailCenter as any).teachers.map((t: any) => (
                          <div key={t.id} className="flex items-center gap-3 p-3 rounded-xl bg-[hsl(var(--muted))]">
                            <div className="w-9 h-9 gradient-primary rounded-xl flex items-center justify-center text-white font-black text-sm">
                              {t.name.charAt(0)}
                            </div>
                            <div className="flex-1 min-w-0">
                              <p className="font-bold text-sm text-[hsl(var(--foreground))] truncate">{t.name}</p>
                              {t.halaqat && t.halaqat.length > 0 && (
                                <p className="text-xs text-[hsl(var(--muted-foreground))]">{t.halaqat.join(' - ')}</p>
                              )}
                            </div>
                            <span className="text-xs font-bold px-2 py-0.5 rounded-full bg-[hsl(var(--primary-light))] text-[hsl(var(--primary))]">
                              {t.students_count || 0} Ø·Ø§Ù„Ø¨
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Actions */}
                  <div className="flex gap-3 pt-2">
                    <button onClick={() => { setDetailCenter(null); openEdit(detailCenter); }}
                      className="flex-1 flex items-center justify-center gap-2 gradient-gold text-white font-bold py-3 rounded-xl hover:opacity-90 transition-all">
                      <Edit2 className="w-4 h-4" /> ØªØ¹Ø¯ÙŠÙ„ Ø§Ù„Ø¨ÙŠØ§Ù†Ø§Øª
                    </button>
                    <button onClick={() => { setDetailCenter(null); handleDelete(detailCenter); }}
                      className="px-4 flex items-center gap-2 bg-red-50 text-red-700 font-bold py-3 rounded-xl hover:bg-red-100 transition-all">
                      <Trash2 className="w-4 h-4" /> Ø­Ø°Ù
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

