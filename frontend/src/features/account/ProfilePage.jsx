import { useState } from 'react';
import { Badge, Field, Notice, PageHeading, Submit } from '../../shared/ui';
import { formatDate } from '../../shared/lib/date';
import { updateProfile } from './api';

export default function ProfilePage({ user, onUser }) {
  const [name, setName] = useState(user.name);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  async function save(e) {
    e.preventDefault(); setBusy(true); setError(''); setMessage('');
    try { const data = await updateProfile({ name: name.trim() }); onUser(data.user); setMessage('Tu perfil se guardó correctamente.'); }
    catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  return <><PageHeading title="Mi perfil">Administra la información de tu cuenta de Cero Colas.</PageHeading><div className="detail-layout"><section className="panel"><h2>Datos de la cuenta</h2><Notice tone="error" focus>{error}</Notice><Notice tone="success" focus>{message}</Notice><form className="stack" onSubmit={save}><Field label="Nombre para tu perfil" autoComplete="name" minLength={2} maxLength={120} value={name} onChange={e => setName(e.target.value)} required /><Field label="Correo electrónico" type="email" value={user.email} readOnly hint="Este correo identifica tu cuenta y se utiliza para recuperar el acceso." /><div><Submit busy={busy}>Guardar cambios</Submit></div></form></section><aside className="context-panel"><h2>Estado de la cuenta</h2><dl className="facts"><div><dt>Estado</dt><dd><Badge tone={user.active ? 'success' : 'warning'}>{user.active ? 'Activa' : 'Inactiva'}</Badge></dd></div><div><dt>Rol</dt><dd>{user.role === 'ADMIN' ? 'Administrador' : 'Paciente'}</dd></div><div><dt>Registro</dt><dd>{formatDate(user.created_at)}</dd></div></dl><p className="muted">Los datos de identidad hospitalaria se consultan durante la sesión y no se editan desde el perfil.</p></aside></div></>;
}
