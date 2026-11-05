import { useState } from 'react';
import { Field, Notice, PageHeading, Submit } from '../../shared/ui';
import { updateProfile } from './api';

export default function PreferencesPage({ user, onUser }) {
  const [preferences, setPreferences] = useState({ email_notifications: false, language: 'es', theme: 'system', ...user.preferences });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  async function save(e) {
    e.preventDefault(); setBusy(true); setError(''); setMessage('');
    try { const data = await updateProfile({ preferences }); onUser(data.user); setMessage('Preferencias guardadas.'); }
    catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  return <><PageHeading title="Preferencias">Ajusta la apariencia y tus preferencias de comunicación.</PageHeading><section className="panel form-panel"><Notice tone="error" focus>{error}</Notice><Notice tone="success" focus>{message}</Notice><form className="stack" onSubmit={save}><Field label="Apariencia" value={preferences.theme} onChange={e => setPreferences(v => ({ ...v, theme: e.target.value }))}><option value="system">Según mi dispositivo</option><option value="light">Clara</option><option value="dark">Oscura</option></Field><Field label="Idioma" value="es" onChange={() => {}} hint="Por ahora el portal está disponible en español."><option value="es">Español</option></Field><label className="check-row"><input type="checkbox" checked={preferences.email_notifications} onChange={e => setPreferences(v => ({ ...v, email_notifications: e.target.checked }))} /><span><strong>Recibir notificaciones por correo</strong><span className="field-hint">Se guarda tu preferencia. El envío de recordatorios estará disponible cuando se integre el módulo de notificaciones.</span></span></label><div><Submit busy={busy}>Guardar preferencias</Submit></div></form></section></>;
}
