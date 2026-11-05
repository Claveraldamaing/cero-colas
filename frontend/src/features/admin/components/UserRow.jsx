import { useState } from 'react';
import { formatDate } from '../../../shared/lib/date';
import { updateUser } from '../api';

export default function UserRow({ item, currentId, onSaved }) {
  const [role, setRole] = useState(item.role);
  const [active, setActive] = useState(item.active);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const own = item.id === currentId;
  async function save() { setBusy(true); setError(''); try { await updateUser(item.id, { role, active }); onSaved(); } catch (e) { setError(e.message); } finally { setBusy(false); } }
  return <tr><td><strong>{item.name}</strong><span className="table-secondary">{item.email}</span>{own && <small>Tu cuenta</small>}</td><td><select aria-label={`Rol de ${item.name}`} value={role} disabled={own || busy} onChange={e => setRole(e.target.value)}><option value="PACIENTE">Paciente</option><option value="ADMIN">Administrador</option></select></td><td><select aria-label={`Estado de ${item.name}`} value={String(active)} disabled={own || busy} onChange={e => setActive(e.target.value === 'true')}><option value="true">Activa</option><option value="false">Inactiva</option></select></td><td>{formatDate(item.created_at)}</td><td><button className="button secondary" disabled={own || busy || (role === item.role && active === item.active)} onClick={save}>{busy ? 'Guardando…' : 'Guardar'}</button>{error && <span role="alert" className="field-error">{error}</span>}</td></tr>;
}
