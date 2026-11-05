import { useState } from 'react';
import { api } from '../shared/api/client';
import { Badge, Field, Notice, PageHeading, Submit } from '../shared/ui';
import { formatDate } from '../shared/lib/date';
import { PASSWORD_HINT, passwordError } from '../shared/validation/password';
export function Profile({ user, onUser }) {
  const [name, setName] = useState(user.name);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  async function save(e) {
    e.preventDefault(); setBusy(true); setError(''); setMessage('');
    try { const data = await api('/auth/profile', { method: 'PATCH', body: { name: name.trim() } }); onUser(data.user); setMessage('Tu perfil se guardó correctamente.'); }
    catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  return <><PageHeading title="Mi perfil">Administra la información de tu cuenta de Cero Colas.</PageHeading><div className="detail-layout"><section className="panel"><h2>Datos de la cuenta</h2><Notice tone="error" focus>{error}</Notice><Notice tone="success" focus>{message}</Notice><form className="stack" onSubmit={save}><Field label="Nombre para tu perfil" autoComplete="name" minLength={2} maxLength={120} value={name} onChange={e => setName(e.target.value)} required /><Field label="Correo electrónico" type="email" value={user.email} readOnly hint="Este correo identifica tu cuenta y se utiliza para recuperar el acceso." /><div><Submit busy={busy}>Guardar cambios</Submit></div></form></section><aside className="context-panel"><h2>Estado de la cuenta</h2><dl className="facts"><div><dt>Estado</dt><dd><Badge tone={user.active ? 'success' : 'warning'}>{user.active ? 'Activa' : 'Inactiva'}</Badge></dd></div><div><dt>Rol</dt><dd>{user.role === 'ADMIN' ? 'Administrador' : 'Paciente'}</dd></div><div><dt>Registro</dt><dd>{formatDate(user.created_at)}</dd></div></dl><p className="muted">Los datos de identidad hospitalaria se consultan durante la sesión y no se editan desde el perfil.</p></aside></div></>;
}
export function Preferences({ user, onUser }) {
  const [preferences, setPreferences] = useState({ email_notifications: false, language: 'es', theme: 'system', ...user.preferences });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  async function save(e) {
    e.preventDefault(); setBusy(true); setError(''); setMessage('');
    try { const data = await api('/auth/profile', { method: 'PATCH', body: { preferences } }); onUser(data.user); setMessage('Preferencias guardadas.'); }
    catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  return <><PageHeading title="Preferencias">Ajusta la apariencia y tus preferencias de comunicación.</PageHeading><section className="panel form-panel"><Notice tone="error" focus>{error}</Notice><Notice tone="success" focus>{message}</Notice><form className="stack" onSubmit={save}><Field label="Apariencia" value={preferences.theme} onChange={e => setPreferences(v => ({ ...v, theme: e.target.value }))}><option value="system">Según mi dispositivo</option><option value="light">Clara</option><option value="dark">Oscura</option></Field><Field label="Idioma" value="es" onChange={() => {}} hint="Por ahora el portal está disponible en español."><option value="es">Español</option></Field><label className="check-row"><input type="checkbox" checked={preferences.email_notifications} onChange={e => setPreferences(v => ({ ...v, email_notifications: e.target.checked }))} /><span><strong>Recibir notificaciones por correo</strong><span className="field-hint">Se guarda tu preferencia. El envío de recordatorios estará disponible cuando se integre el módulo de notificaciones.</span></span></label><div><Submit busy={busy}>Guardar preferencias</Submit></div></form></section></>;
}
export function Security({ onUser }) {
  const [form, setForm] = useState({ current_password: '', new_password: '', confirmation: '' });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const change = key => e => setForm(v => ({ ...v, [key]: e.target.value }));
  async function save(e) {
    e.preventDefault(); setError(''); setMessage('');
    if (passwordError(form.new_password)) { setError(passwordError(form.new_password)); return; }
    if (form.new_password !== form.confirmation) { setError('Las nuevas contraseñas no coinciden.'); return; }
    setBusy(true);
    try { const data = await api('/auth/change-password', { method: 'POST', body: { current_password: form.current_password, new_password: form.new_password } }); if (data.user) onUser(data.user); setForm({ current_password: '', new_password: '', confirmation: '' }); setMessage(data.message || 'Contraseña actualizada.'); }
    catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  return <><PageHeading title="Seguridad">Actualiza la contraseña que utilizas para acceder al portal.</PageHeading><div className="detail-layout"><section className="panel"><h2>Cambiar contraseña</h2><Notice tone="error" focus>{error}</Notice><Notice tone="success" focus>{message}</Notice><form className="stack" onSubmit={save}><Field label="Contraseña actual" type="password" autoComplete="current-password" value={form.current_password} onChange={change('current_password')} maxLength={128} required /><Field label="Nueva contraseña" type="password" autoComplete="new-password" value={form.new_password} onChange={change('new_password')} maxLength={128} hint={PASSWORD_HINT} required /><Field label="Confirma la nueva contraseña" type="password" autoComplete="new-password" value={form.confirmation} onChange={change('confirmation')} maxLength={128} required /><div><Submit busy={busy}>Actualizar contraseña</Submit></div></form></section><aside className="context-panel"><h2>Tu sesión</h2><p>Al terminar, cierra tu sesión desde el menú. Es especialmente importante si utilizas un equipo compartido.</p><p className="muted">La sesión de Cero Colas y la identificación hospitalaria tienen vencimientos independientes. El portal te pedirá volver a identificarte cuando sea necesario.</p></aside></div></>;
}
