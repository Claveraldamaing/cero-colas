import { useEffect, useId, useRef, useState } from 'react';
import { AlertCircle, CheckCircle2, Info, RefreshCw } from 'lucide-react';
import { api } from '../api/client';
export function Notice({ children, tone = 'info', focus = false }) {
  const ref = useRef(null);
  useEffect(() => { if (focus) ref.current?.focus(); }, [children, focus]);
  if (!children) return null;
  const Icon = tone === 'error' ? AlertCircle : tone === 'success' ? CheckCircle2 : Info;
  return <div ref={ref} tabIndex={focus ? -1 : undefined} className={`notice ${tone}`} role={tone === 'error' ? 'alert' : 'status'}><Icon size={19} aria-hidden="true" /><div>{children}</div></div>;
}
export function Field({ label, hint, error, children, ...props }) {
  const id = useId();
  return <div className="field"><label htmlFor={id}>{label}</label>{children
    ? <select id={id} aria-describedby={hint || error ? `${id}-help` : undefined} aria-invalid={!!error} {...props}>{children}</select>
    : <input id={id} aria-describedby={hint || error ? `${id}-help` : undefined} aria-invalid={!!error} {...props} />}
    {(hint || error) && <span id={`${id}-help`} className={error ? 'field-error' : 'field-hint'}>{error || hint}</span>}</div>;
}
export function Submit({ busy, children, ...props }) {
  return <button type="submit" className="button primary" disabled={busy} aria-busy={busy} {...props}>{busy ? <><RefreshCw className="spin" size={17} aria-hidden="true" />Procesando…</> : children}</button>;
}
export function Challenge({ value, onChange, refreshKey = 0, purpose = 'continuar' }) {
  const [challenge, setChallenge] = useState(null);
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    // Clear an obsolete server challenge before the replacement request completes.
    // oxlint-disable-next-line react/set-state-in-effect
    setChallenge(null); setError(''); onChange({ challenge_id: '', challenge_answer: '' });
    api('/auth/challenge', { signal: controller.signal, silentUnauthorized: true }).then(data => {
      setChallenge(data); onChange({ challenge_id: data.challenge_id, challenge_answer: '' });
    }).catch(e => { if (e.name !== 'AbortError') setError(e.message); });
    return () => controller.abort();
  }, [refreshKey, retry, onChange]);
  return <div className="challenge"><div className="challenge-heading"><strong>Verificación de acceso</strong><button type="button" className="text-button" onClick={() => setRetry(v => v + 1)} aria-label="Obtener otra pregunta de verificación"><RefreshCw size={16} aria-hidden="true" />Cambiar</button></div>
    {error ? <Notice tone="error">{error}</Notice> : challenge ? <Field label={challenge.prompt} type="text" inputMode="numeric" autoComplete="off" maxLength={5} required value={value.challenge_answer} onChange={e => onChange({ challenge_id: challenge.challenge_id, challenge_answer: e.target.value })} /> : <div className="skeleton short" aria-label="Cargando verificación" />}
    <p className="field-hint">Responde para {purpose}. {challenge?.mode === 'development_arithmetic' ? 'Verificación aritmética de desarrollo; no equivale a un CAPTCHA de producción.' : ''}</p></div>;
}
export function PageHeading({ title, children, action }) {
  return <div className="page-heading"><div><h1 tabIndex={-1}>{title}</h1>{children && <p>{children}</p>}</div>{action}</div>;
}
export function Skeleton({ label = 'Cargando información' }) {
  return <div className="loading-content" role="status" aria-label={label}><div className="skeleton short" /><div className="skeleton" /><div className="skeleton" /><span className="sr-only">{label}</span></div>;
}
export function LoadError({ error, retry }) {
  return <div className="stack"><Notice tone="error">{error}</Notice><button className="button secondary" onClick={retry}><RefreshCw size={17} aria-hidden="true" />Volver a intentar</button></div>;
}
export function Badge({ children, tone = 'neutral' }) { return <span className={`badge ${tone}`}>{children}</span>; }
