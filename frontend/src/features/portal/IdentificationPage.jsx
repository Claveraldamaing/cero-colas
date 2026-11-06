import { useEffect, useState } from 'react';
import { RefreshCw } from 'lucide-react';
import { Challenge, Field, LoadError, Notice, PageHeading, Skeleton, Submit } from '../../shared/ui';
import { SourceNotice } from '../../shared/ui/SourceNotice';
import { useResource } from '../../shared/hooks/useResource';
import { clearIdentity, getEligibility, identifyPatient, portalPaths } from './api';
import EligibilityDetails from './components/EligibilityDetails';

export default function IdentificationPage({ onChanged, revision, onReserve }) {
  const initial = useResource(portalPaths.dashboard, revision);
  const policies = useResource(portalPaths.policies);
  const [identity, setIdentity] = useState(null);
  const [eligibility, setEligibility] = useState(null);
  const [source, setSource] = useState(null);
  const [form, setForm] = useState({ numero_documento: '', fecha_nacimiento: '', consent: false });
  const [challenge, setChallenge] = useState({ challenge_id: '', challenge_answer: '' });
  const [challengeRevision, setChallengeRevision] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [remaining, setRemaining] = useState(0);
  // Synchronize a completed server fetch with this form's interactive identity state.
  // oxlint-disable-next-line react/set-state-in-effect
  useEffect(() => { if (initial.data) { setIdentity(initial.data.identity); setEligibility(initial.data.eligibility); setSource(initial.data.source); } }, [initial.data]);
  useEffect(() => {
    if (!identity?.identified) return;
    const expires = identity.expires_at ? new Date(identity.expires_at).getTime() : Date.now() + (identity.seconds_remaining || 0) * 1000;
    const tick = () => {
      const seconds = Math.max(0, Math.ceil((expires - Date.now()) / 1000)); setRemaining(seconds);
      if (!seconds) { setIdentity(null); setEligibility(null); setMessage('La identificación hospitalaria venció. Identifica nuevamente al paciente para continuar.'); }
    };
    tick(); const timer = setInterval(tick, 1000); return () => clearInterval(timer);
  }, [identity]);
  async function queryEligibility() {
    setBusy(true); setError('');
    try { const data = await getEligibility(true); setEligibility(data.eligibility); setIdentity(data.identity); setSource(data.source); onChanged(); }
    catch (e) { setError(e.message); if (e.status === 401 || e.status === 410) { setIdentity(null); setEligibility(null); } }
    finally { setBusy(false); }
  }
  async function identify(e) {
    e.preventDefault(); setBusy(true); setError(''); setMessage('');
    try {
      const data = await identifyPatient({ ...form, ...challenge });
      setIdentity(data.identity); setEligibility(null); setSource(data.source);
      setForm({ numero_documento: '', fecha_nacimiento: '', consent: false });
      try { const evaluated = await getEligibility(); setEligibility(evaluated.eligibility); setIdentity(evaluated.identity); }
      catch (e) { setError(e.message); if (e.status === 401 || e.status === 410) setIdentity(null); }
      onChanged();
    } catch (e) { setError(e.message); }
    finally { setBusy(false); setChallengeRevision(v => v + 1); }
  }
  async function clearPatient() {
    setBusy(true); setError('');
    try { await clearIdentity(); setIdentity(null); setEligibility(null); setMessage('Identificación cerrada. Puedes consultar a otro paciente.'); onChanged(); }
    catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  const [today] = useState(() => new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Lima', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date()));
  return <><PageHeading title="Identificación y elegibilidad">Consulta las condiciones para acceder a una reserva en línea.</PageHeading><SourceNotice source={source || policies.data?.source} /><Notice tone="error" focus>{error}</Notice><Notice tone="success" focus>{message}</Notice>
    {initial.loading ? <Skeleton /> : initial.error ? <LoadError error={initial.error} retry={initial.reload} /> : identity?.identified ? <><section className="identity-bar"><div><strong>{identity.paciente?.nombre_enmascarado || 'Paciente identificado'}</strong><span>{identity.paciente?.edad != null ? `${identity.paciente.edad} años · ` : ''}Identificación vigente por {Math.floor(remaining / 60)}:{String(remaining % 60).padStart(2, '0')}</span></div><button className="button secondary" disabled={busy} onClick={clearPatient}>Cambiar paciente</button></section><section className="panel"><div className="section-heading"><h2>Resultado de la consulta</h2><button className="text-button" disabled={busy} onClick={queryEligibility}><RefreshCw size={16} className={busy ? 'spin' : ''} aria-hidden="true" />{busy ? 'Consultando…' : 'Actualizar'}</button></div><EligibilityDetails eligibility={eligibility} />{!eligibility && !busy && <button className="button primary" onClick={queryEligibility}>Consultar elegibilidad</button>}{eligibility?.reserve_ready && <button className="button primary" onClick={() => onReserve(eligibility)}>Iniciar reserva</button>}{eligibility && !eligibility.reserve_ready && <button className="button secondary" onClick={() => onReserve(eligibility)}>Ver pasos de reserva (vista previa)</button>}</section>{eligibility?.reserve_ready ? <Notice>{eligibility.reservation_simulation ? 'Reserva de prueba habilitada: las citas se crean únicamente en el simulador local y no son reales.' : 'La reserva se confirmará con el servicio hospitalario; revisar disponibilidad no garantiza que un cupo siga libre.'}</Notice> : <Notice>La reserva real permanece bloqueada hasta confirmar los requisitos. Puedes recorrer los pasos en vista previa, sin consultar cupos reales ni crear una cita.</Notice>}</> : <div className="detail-layout"><section className="panel"><h2>Datos del paciente</h2><form className="stack" onSubmit={identify}><Field label="DNI" type="text" inputMode="numeric" autoComplete="off" pattern="[0-9]{8}" maxLength={8} minLength={8} value={form.numero_documento} onChange={e => setForm(v => ({ ...v, numero_documento: e.target.value.replace(/\D/g, '') }))} hint="Ingresa los 8 dígitos del documento." required /><Field label="Fecha de nacimiento" type="date" autoComplete="off" max={today} value={form.fecha_nacimiento} onChange={e => setForm(v => ({ ...v, fecha_nacimiento: e.target.value }))} required />
      {policies.loading ? <Skeleton label="Cargando aviso de privacidad" /> : policies.error ? <LoadError error={policies.error} retry={policies.reload} /> : <><div className="privacy-text"><h3>Antes de consultar</h3><p>{policies.data?.privacy_notice || 'El DNI y la fecha de nacimiento se utilizan únicamente para identificar al paciente durante esta sesión.'}</p>{!policies.data?.privacy_approved && <p className="field-hint">Aviso provisional para el prototipo. Utiliza únicamente datos de prueba mientras no exista aprobación institucional.</p>}</div><label className="check-row"><input type="checkbox" checked={form.consent} onChange={e => setForm(v => ({ ...v, consent: e.target.checked }))} required /><span>He leído el aviso y autorizo la consulta de los datos del paciente.</span></label></>}
      <Challenge value={challenge} onChange={setChallenge} refreshKey={challengeRevision} purpose="consultar al paciente" /><div><Submit busy={busy} disabled={busy || !challenge.challenge_id || !policies.data || !form.consent}>Identificar y consultar</Submit></div></form></section><aside className="context-panel"><h2>Qué podrás consultar</h2><ul className="plain-list"><li>Estado de afiliación al SIS.</li><li>Condición del paciente.</li><li>Referencias y especialidades disponibles.</li><li>Próxima fecha permitida para reservar.</li></ul><p className="muted">Crear una cuenta no registra al paciente en el hospital ni garantiza su elegibilidad. El resultado depende del servicio hospitalario.</p></aside></div>}
  </>;
}
