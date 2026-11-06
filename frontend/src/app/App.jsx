import { useEffect, useRef, useState } from 'react';
import { HeartPulse, LogOut, Menu, X } from 'lucide-react';
import { setCsrf, setSessionExpiredHandler } from '../shared/api/client';
import AuthPage from '../features/auth/AuthPage';
import { getSession, logout as logoutRequest } from '../features/auth/api';
import ProfilePage from '../features/account/ProfilePage';
import PreferencesPage from '../features/account/PreferencesPage';
import SecurityPage from '../features/account/SecurityPage';
import DashboardPage from '../features/portal/DashboardPage';
import IdentificationPage from '../features/portal/IdentificationPage';
import SurveysPage from '../features/surveys/SurveysPage';
import AdminDashboardPage from '../features/admin/AdminDashboardPage';
import UserManagementPage from '../features/admin/UserManagementPage';
import ReservationWizard from '../features/reservations/ReservationWizard';
import { Notice, Skeleton } from '../shared/ui';
import { navigationFor } from './navigation';
import '../styles/p1.css';

export default function App() {
  const [user, setUser] = useState(null);
  const [resetMode] = useState(() => new URLSearchParams(window.location.search).has('reset_token') || new URLSearchParams(window.location.search).has('reset'));
  const [loading, setLoading] = useState(!resetMode);
  const [view, setView] = useState('dashboard');
  const [reservationEligibility, setReservationEligibility] = useState(null);
  const [revision, setRevision] = useState(0);
  const [error, setError] = useState('');
  const [expired, setExpired] = useState('');
  const [menu, setMenu] = useState(false);
  const [busy, setBusy] = useState(false);
  const main = useRef(null);
  const changed = () => setRevision(n => n + 1);
  useEffect(() => {
    setSessionExpiredHandler(() => { setUser(null); setCsrf(null); setExpired('Tu sesión terminó. Inicia sesión nuevamente.'); });
    if (resetMode) {
      return () => setSessionExpiredHandler(() => {});
    }
    const controller = new AbortController();
    getSession({ signal: controller.signal }).then(data => setUser(data.user))
      .catch(e => { if (e.name !== 'AbortError' && e.status !== 401) setError(e.message); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => { controller.abort(); setSessionExpiredHandler(() => {}); };
  }, [resetMode]);
  useEffect(() => {
    const media = window.matchMedia('(prefers-color-scheme: dark)');
    const apply = () => document.documentElement.dataset.theme = (user?.preferences?.theme || 'system') === 'system' ? (media.matches ? 'dark' : 'light') : user.preferences.theme;
    apply(); media.addEventListener('change', apply); return () => media.removeEventListener('change', apply);
  }, [user?.preferences?.theme]);
  function navigate(next, payload) { if (next === 'reservation') setReservationEligibility(payload); setView(next); setMenu(false); setError(''); window.scrollTo({ top: 0 }); requestAnimationFrame(() => main.current?.querySelector('h1')?.focus()); }
  function authenticated(account) { setUser(account); setExpired(''); setError(''); setView(account.role === 'ADMIN' ? 'admin' : 'dashboard'); }
  async function logout() { setBusy(true); try { await logoutRequest(); setUser(null); setCsrf(null); setView('dashboard'); setError(''); } catch (e) { setError(e.message); } finally { setBusy(false); } }
  if (loading) return <div className="initial-load"><HeartPulse size={34} aria-hidden="true" /><Skeleton label="Comprobando tu sesión" /></div>;
  if (!user) return <><Notice tone="error">{error}</Notice><AuthPage onAuthenticated={authenticated} expiredMessage={expired} /></>;
  const nav = navigationFor(user);
  let page;
  switch (view) {
    case 'profile': page = <ProfilePage user={user} onUser={setUser} />; break;
    case 'preferences': page = <PreferencesPage user={user} onUser={setUser} />; break;
    case 'security': page = <SecurityPage onUser={setUser} />; break;
    case 'identify': page = <IdentificationPage revision={revision} onChanged={changed} onReserve={eligibility => navigate('reservation', eligibility)} />; break;
    case 'reservation': page = <ReservationWizard eligibility={reservationEligibility} onExit={() => navigate('identify')} />; break;
    case 'surveys': page = <SurveysPage navigate={navigate} onChanged={changed} />; break;
    case 'admin': page = user.role === 'ADMIN' ? <AdminDashboardPage revision={revision} navigate={navigate} /> : <Notice tone="error">No tienes acceso a esta vista.</Notice>; break;
    case 'users': page = user.role === 'ADMIN' ? <UserManagementPage user={user} onChanged={changed} /> : <Notice tone="error">No tienes acceso a esta vista.</Notice>; break;
    default: page = <DashboardPage user={user} navigate={navigate} revision={revision} />;
  }
  return <div className="app-shell"><a href="#main-content" className="skip-link">Ir al contenido</a><header className="mobile-header"><span className="brand"><HeartPulse size={25} />Cero Colas</span><button className="icon-button" aria-label={menu ? 'Cerrar menú' : 'Abrir menú'} aria-expanded={menu} onClick={() => setMenu(!menu)}>{menu ? <X /> : <Menu />}</button></header>
    <aside className={`sidebar ${menu ? 'open' : ''}`}><button className="brand" onClick={() => navigate(user.role === 'ADMIN' ? 'admin' : 'dashboard')}><HeartPulse size={30} aria-hidden="true" /><span>Cero Colas</span></button><p className="sidebar-description">Portal del paciente</p><nav aria-label="Menú principal">{nav.map(([key, title, Icon]) => <button key={key} className={view === key ? 'nav-item active' : 'nav-item'} aria-current={view === key ? 'page' : undefined} onClick={() => navigate(key)}><Icon size={19} aria-hidden="true" />{title}</button>)}</nav><div className="sidebar-bottom"><strong>{user.name}</strong><span>{user.role === 'ADMIN' ? 'Administrador' : 'Cuenta de paciente'}</span><button className="nav-item" disabled={busy} onClick={logout}><LogOut size={18} aria-hidden="true" />{busy ? 'Cerrando…' : 'Cerrar sesión'}</button><small>Prototipo académico · P1</small></div></aside>
    <main id="main-content" className="workspace" ref={main}><div className="workspace-top"><span>Usuarios, identificación y satisfacción</span><span className="account-state"><span />Cuenta activa</span></div><Notice tone="error" focus>{error}</Notice><div key={view} className="page-content">{page}</div><footer className="workspace-footer">Cero Colas · Consulta externa<br /><span>La información hospitalaria depende del servicio conectado.</span></footer></main>
  </div>;
}
