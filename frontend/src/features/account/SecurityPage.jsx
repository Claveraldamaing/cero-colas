import { useState } from 'react';
import { Field, Notice, PageHeading, Submit } from '../../shared/ui';
import { PASSWORD_HINT, passwordError } from '../../shared/validation/password';
import { changePassword } from './api';

export default function SecurityPage({ onUser }) {
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
    try { const data = await changePassword({ current_password: form.current_password, new_password: form.new_password }); if (data.user) onUser(data.user); setForm({ current_password: '', new_password: '', confirmation: '' }); setMessage(data.message || 'Contraseña actualizada.'); }
    catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  return <><PageHeading title="Seguridad">Actualiza la contraseña que utilizas para acceder al portal.</PageHeading><div className="detail-layout"><section className="panel"><h2>Cambiar contraseña</h2><Notice tone="error" focus>{error}</Notice><Notice tone="success" focus>{message}</Notice><form className="stack" onSubmit={save}><Field label="Contraseña actual" type="password" autoComplete="current-password" value={form.current_password} onChange={change('current_password')} maxLength={128} required /><Field label="Nueva contraseña" type="password" autoComplete="new-password" value={form.new_password} onChange={change('new_password')} maxLength={128} hint={PASSWORD_HINT} required /><Field label="Confirma la nueva contraseña" type="password" autoComplete="new-password" value={form.confirmation} onChange={change('confirmation')} maxLength={128} required /><div><Submit busy={busy}>Actualizar contraseña</Submit></div></form></section><aside className="context-panel"><h2>Tu sesión</h2><p>Al terminar, cierra tu sesión desde el menú. Es especialmente importante si utilizas un equipo compartido.</p><p className="muted">La sesión de Cero Colas y la identificación hospitalaria tienen vencimientos independientes. El portal te pedirá volver a identificarte cuando sea necesario.</p></aside></div></>;
}
