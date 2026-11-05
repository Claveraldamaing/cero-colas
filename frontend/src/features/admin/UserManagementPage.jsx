import { useState } from 'react';
import { Search } from 'lucide-react';
import { Field, LoadError, Notice, PageHeading, Skeleton } from '../../shared/ui';
import { useResource } from '../../shared/hooks/useResource';
import { usersPath } from './api';
import UserRow from './components/UserRow';

export default function UserManagementPage({ user, onChanged }) {
  const [search, setSearch] = useState('');
  const [query, setQuery] = useState('');
  const [offset, setOffset] = useState(0);
  const [saved, setSaved] = useState('');
  const { data, loading, error, reload } = useResource(usersPath(offset, query));
  function onSaved() { setSaved('El usuario fue actualizado. Los cambios de rol o desactivación cierran sus sesiones.'); reload(); onChanged(); }
  return <><PageHeading title="Administración de usuarios">Gestiona los permisos y el estado de las cuentas locales.</PageHeading><Notice tone="success">{saved}</Notice><section className="panel"><form className="search-form" onSubmit={e => { e.preventDefault(); setOffset(0); setQuery(search.trim()); }}><Field label="Buscar por nombre o correo" value={search} maxLength={120} onChange={e => setSearch(e.target.value)} /><button className="button primary" type="submit"><Search size={17} />Buscar</button></form>{loading ? <Skeleton /> : error ? <LoadError error={error} retry={reload} /> : <><div className="table-scroll" tabIndex={0} role="region" aria-label="Lista de usuarios"><table><thead><tr><th>Usuario</th><th>Rol</th><th>Estado</th><th>Registro</th><th>Acciones</th></tr></thead><tbody>{data.items.map(item => <UserRow key={`${item.id}-${item.role}-${item.active}`} item={item} currentId={user.id} onSaved={onSaved} />)}</tbody></table></div>{!data.items.length && <p className="empty-state">No hay usuarios que coincidan con la búsqueda.</p>}<div className="pagination"><span>{data.total} usuarios · Página {Math.floor(offset / 20) + 1}</span><div><button className="button secondary" disabled={offset === 0} onClick={() => setOffset(n => Math.max(0, n - 20))}>Anterior</button><button className="button secondary" disabled={offset + 20 >= data.total} onClick={() => setOffset(n => n + 20)}>Siguiente</button></div></div></>}</section></>;
}
