/* oxlint-disable react/only-export-components -- Shared password validation accompanies the account forms. */
import { useEffect, useState } from 'react';
import { ArrowLeft, HeartPulse, LockKeyhole } from 'lucide-react';
import { api } from './api';
import { Challenge, Field, Notice, Submit } from './ui';
export const PASSWORD_HINT = 'Entre 10 y 128 caracteres, con una mayúscula, una minúscula y un número.';
export function passwordError(value) {
  return value.length < 10 || value.length > 128 || !/[A-Z]/.test(value) || !/[a-z]/.test(value) || !/\d/.test(value) ? PASSWORD_HINT : '';
}
export default function Auth({ onAuthenticated, expiredMessage }) {
  const [resetToken] = useState(() => new URLSearchParams(window.location.search).get('reset_token') || new URLSearchParams(window.location.search).get('reset'));
  useEffect(() => { if (resetToken) window.history.replaceState({}, '', window.location.pathname); }, [resetToken]);
  const [mode, setMode] = useState(resetToken ? 'reset' : 'login');
  const [form, setForm] = useState({ name: '', email: '', password: '', confirm: '' });
  const [challenge, setChallenge] = useState({ challenge_id: '', challenge_answer: '' });
  const [challengeRevision, setChallengeRevision] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const change = key => e => setForm(v => ({ ...v, [key]: e.target.value }));
  const switchMode = next => {
    setMode(next); setError(''); setMessage(''); setForm(v => ({ ...v, password: '', confirm: '' })); setChallengeRevision(v => v + 1);
    if (next !== 'reset' && resetToken) window.history.replaceState({}, '', window.location.pathname);
  };
  async function submit(e) {
    e.preventDefault(); setError(''); setMessage('');
    if (['register', 'reset'].includes(mode)) {
      const invalid = passwordError(form.password);
      if (invalid) { setError(invalid); return; }
      if (form.password !== form.confirm) { setError('Las contraseñas no coinciden. Revisa la confirmación.'); return; }
    }
    setBusy(true);
    try {
      if (mode === 'forgot') {
        const data = await api('/auth/forgot-password', { method: 'POST', body: { email: form.email.trim(), ...challenge }, silentUnauthorized: true });
        setMessage(data.message || 'Si existe una cuenta con ese correo, recibirás instrucciones para recuperar el acceso.'); setChallengeRevision(v => v + 1);
      } else if (mode === 'reset') {
        const data = await api('/auth/reset-password', { method: 'POST', body: { token: resetToken, new_password: form.password }, silentUnauthorized: true });
        switchMode('login'); setMessage(data.message || 'Contraseña actualizada. Ya puedes iniciar sesión.');
      } else {
        const body = { email: form.email.trim(), password: form.password, ...challenge, ...(mode === 'register' ? { name: form.name.trim() } : {}) };
        const data = await api(`/auth/${mode}`, { method: 'POST', body, silentUnauthorized: true }); onAuthenticated(data.user);
      }
    } catch (e) { setError(e.message); setChallengeRevision(v => v + 1); }
    finally { setBusy(false); }
  }
  const titles = { login: 'Ingresa a tu cuenta', register: 'Crea tu cuenta', forgot: 'Recupera tu acceso', reset: 'Elige una nueva contraseña' };
  return <div className="auth-layout"><aside className="auth-aside"><a className="brand" href="#login"><HeartPulse size={29} aria-hidden="true" /><span>Cero Colas</span></a><div className="auth-intro"><h1>Tu información.<br />Un acceso seguro.</h1><p>Consulta tu elegibilidad, revisa tu perfil y comparte cómo fue tu experiencia.</p><div className="auth-process"><span><span className="step-number">1</span> Ingresa a tu cuenta</span><span><span className="step-number">2</span> Identifica al paciente</span><span><span className="step-number">3</span> Consulta su elegibilidad</span></div></div><p className="auth-footnote">Prototipo académico · Módulo de usuarios y atención al paciente</p></aside>
    <main className="auth-main" id="main-content"><div className="auth-form-wrap"><span className="auth-lock"><LockKeyhole size={23} aria-hidden="true" /></span><h2>{titles[mode]}</h2><p className="muted">{mode === 'register' ? 'La cuenta te permite acceder al portal. La validación hospitalaria se realiza después.' : mode === 'forgot' ? 'Escribe el correo asociado a tu cuenta.' : mode === 'reset' ? 'El enlace de recuperación solo se puede utilizar una vez.' : 'Accede con el correo y la contraseña de Cero Colas.'}</p>
      <Notice tone="info">{expiredMessage && mode === 'login' ? expiredMessage : null}</Notice><Notice tone="error" focus>{error}</Notice><Notice tone="success" focus>{message}</Notice>
      <form className="stack" onSubmit={submit}>
        {mode === 'register' && <Field label="Nombre para tu perfil" autoComplete="name" value={form.name} onChange={change('name')} minLength={2} maxLength={120} required />}
        {mode !== 'reset' && <Field label="Correo electrónico" type="email" autoComplete="username" value={form.email} onChange={change('email')} maxLength={254} required />}
        {mode !== 'forgot' && <Field label={mode === 'reset' ? 'Nueva contraseña' : 'Contraseña'} type="password" autoComplete={mode === 'login' ? 'current-password' : 'new-password'} value={form.password} onChange={change('password')} maxLength={128} required hint={mode !== 'login' ? PASSWORD_HINT : undefined} />}
        {['register', 'reset'].includes(mode) && <Field label="Confirma la contraseña" type="password" autoComplete="new-password" value={form.confirm} onChange={change('confirm')} maxLength={128} required />}
        {mode !== 'reset' && <Challenge value={challenge} onChange={setChallenge} refreshKey={`${mode}-${challengeRevision}`} purpose={mode === 'forgot' ? 'solicitar la recuperación' : 'acceder'} />}
        <Submit busy={busy} disabled={busy || (mode !== 'reset' && !challenge.challenge_id)}>{({ login: 'Iniciar sesión', register: 'Crear cuenta', forgot: 'Solicitar recuperación', reset: 'Guardar contraseña' })[mode]}</Submit>
      </form>
      <div className="auth-links">{mode === 'login' ? <><button className="text-button" onClick={() => switchMode('forgot')}>Olvidé mi contraseña</button><p>¿Primera vez aquí? <button className="text-button" onClick={() => switchMode('register')}>Crear una cuenta</button></p></> : <button className="text-button" onClick={() => switchMode('login')}><ArrowLeft size={16} aria-hidden="true" />Volver a iniciar sesión</button>}</div>
      {mode === 'forgot' && <p className="field-hint">En desarrollo, los mensajes se entregan al buzón local configurado por el equipo. No se envían correos si el servicio de correo no está configurado.</p>}
    </div></main></div>;
}
