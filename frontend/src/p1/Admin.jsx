import { useState } from 'react';
import { ArrowRight, RefreshCw, Search } from 'lucide-react';
import { api } from '../shared/api/client';
import { Badge, Field, LoadError, Notice, PageHeading, Skeleton } from '../shared/ui';
import { SourceNotice } from '../shared/ui/SourceNotice';
import { useResource } from '../shared/hooks/useResource';
import { formatDate } from '../shared/lib/date';

export function AdminDashboard({ revision, navigate }) {
  const { data, loading, error, reload } = useResource('/portal/admin/dashboard', revision);
  if (loading) return <Skeleton />;
  if (error) return <LoadError error={error} retry={reload} />;
  const survey = data.survey;
  const value = n => n == null ? 'Sin respuestas' : `${n} / ${survey.scale.max}`;
  return <><PageHeading title="Resumen general" action={<button className="button secondary" onClick={reload}><RefreshCw size={16} />Actualizar</button>}>Usuarios, disponibilidad del servicio y experiencia de uso.</PageHeading><SourceNotice source={data.source} />
    <section className="panel"><div className="section-heading"><h2>Usuarios registrados</h2><button className="text-button" onClick={() => navigate('users')}>Administrar usuarios<ArrowRight size={16} /></button></div><dl className="summary-strip"><div><dt>Total de cuentas</dt><dd>{data.users.total}</dd></div><div><dt>Activas</dt><dd>{data.users.active}</dd></div><div><dt>Inactivas</dt><dd>{data.users.inactive}</dd></div><div><dt>Administradores</dt><dd>{data.users.admins}</dd></div></dl></section>
    <div className="dashboard-columns"><section className="panel"><h2>Estado de la integración</h2><dl className="facts"><div><dt>API hospitalaria</dt><dd><Badge tone={data.service.available ? 'success' : 'warning'}>{data.service.available ? 'Disponible' : 'No disponible'}</Badge></dd></div><div><dt>Canal de citas</dt><dd>{data.service.canal_abierto == null ? 'Sin información' : data.service.canal_abierto ? 'Abierto' : 'Cerrado'}</dd></div><div><dt>Verificación SIS</dt><dd>{data.service.verificacion_sis || 'Sin información'}</dd></div><div><dt>Hora informada por el servicio</dt><dd>{formatDate(data.service.hora_servidor, true)}</dd></div></dl>{data.service.error && <Notice tone="warning">{data.service.error.message}</Notice>}</section><section className="panel"><h2>Actividad de otros módulos</h2><dl className="facts">{[['reservations', 'Reservas gestionadas'], ['cancellations', 'Anulaciones'], ['tickets', 'Tickets de soporte'], ['chatbot', 'Uso del chatbot']].map(([key, title]) => <div key={key}><dt>{title}</dt><dd>{data.metrics[key] == null ? <Badge>Sin integrar</Badge> : data.metrics[key]}</dd></div>)}</dl><p className="field-hint">Estos indicadores se completarán con los datos de los módulos de reservas, gestión de citas y soporte.</p></section></div>
    <section className="panel"><div className="section-heading"><h2>Satisfacción de usuarios</h2><Badge>{survey.responses} respuestas</Badge></div><p className="muted">Resultados guardados en la base de Cero Colas. Escala del prototipo: {survey.scale.min} a {survey.scale.max}.</p><div className="survey-summary"><dl className="facts"><div><dt>Facilidad de uso promedio</dt><dd>{value(survey.average_ease)}</dd></div><div><dt>Satisfacción promedio</dt><dd>{value(survey.average_satisfaction)}</dd></div></dl><div className="distribution" aria-label="Distribución de satisfacción">{survey.distribution.map(row => <div key={row.score}><span>{row.score} puntos</span><meter min="0" max={Math.max(survey.responses, 1)} value={row.count} aria-label={`${row.score} puntos: ${row.count} respuestas`} /><strong>{row.count}</strong></div>)}</div></div>{!survey.responses && <p className="muted">Los promedios aparecerán cuando se reciba la primera encuesta.</p>}</section></>;
}

function UserRow({ item, currentId, onSaved }) {
  const [role, setRole] = useState(item.role);
  const [active, setActive] = useState(item.active);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const own = item.id === currentId;
  async function save() { setBusy(true); setError(''); try { await api(`/admin/users/${item.id}`, { method: 'PATCH', body: { role, active } }); onSaved(); } catch (e) { setError(e.message); } finally { setBusy(false); } }
  return <tr><td><strong>{item.name}</strong><span className="table-secondary">{item.email}</span>{own && <small>Tu cuenta</small>}</td><td><select aria-label={`Rol de ${item.name}`} value={role} disabled={own || busy} onChange={e => setRole(e.target.value)}><option value="PACIENTE">Paciente</option><option value="ADMIN">Administrador</option></select></td><td><select aria-label={`Estado de ${item.name}`} value={String(active)} disabled={own || busy} onChange={e => setActive(e.target.value === 'true')}><option value="true">Activa</option><option value="false">Inactiva</option></select></td><td>{formatDate(item.created_at)}</td><td><button className="button secondary" disabled={own || busy || (role === item.role && active === item.active)} onClick={save}>{busy ? 'Guardando…' : 'Guardar'}</button>{error && <span role="alert" className="field-error">{error}</span>}</td></tr>;
}

export function UserManagement({ user, onChanged }) {
  const [search, setSearch] = useState('');
  const [query, setQuery] = useState('');
  const [offset, setOffset] = useState(0);
  const [saved, setSaved] = useState('');
  const { data, loading, error, reload } = useResource(`/admin/users?limit=20&offset=${offset}&q=${encodeURIComponent(query)}`);
  function onSaved() { setSaved('El usuario fue actualizado. Los cambios de rol o desactivación cierran sus sesiones.'); reload(); onChanged(); }
  return <><PageHeading title="Administración de usuarios">Gestiona los permisos y el estado de las cuentas locales.</PageHeading><Notice tone="success">{saved}</Notice><section className="panel"><form className="search-form" onSubmit={e => { e.preventDefault(); setOffset(0); setQuery(search.trim()); }}><Field label="Buscar por nombre o correo" value={search} maxLength={120} onChange={e => setSearch(e.target.value)} /><button className="button primary" type="submit"><Search size={17} />Buscar</button></form>{loading ? <Skeleton /> : error ? <LoadError error={error} retry={reload} /> : <><div className="table-scroll" tabIndex={0} role="region" aria-label="Lista de usuarios"><table><thead><tr><th>Usuario</th><th>Rol</th><th>Estado</th><th>Registro</th><th>Acciones</th></tr></thead><tbody>{data.items.map(item => <UserRow key={`${item.id}-${item.role}-${item.active}`} item={item} currentId={user.id} onSaved={onSaved} />)}</tbody></table></div>{!data.items.length && <p className="empty-state">No hay usuarios que coincidan con la búsqueda.</p>}<div className="pagination"><span>{data.total} usuarios · Página {Math.floor(offset / 20) + 1}</span><div><button className="button secondary" disabled={offset === 0} onClick={() => setOffset(n => Math.max(0, n - 20))}>Anterior</button><button className="button secondary" disabled={offset + 20 >= data.total} onClick={() => setOffset(n => n + 20)}>Siguiente</button></div></div></>}</section></>;
}
