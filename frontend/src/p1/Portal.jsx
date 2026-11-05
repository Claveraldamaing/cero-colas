import { useEffect, useState } from 'react';
import { ArrowRight, CalendarDays, ClipboardCheck, RefreshCw, ShieldCheck } from 'lucide-react';
import { api } from './api';
import { Badge, Challenge, Field, LoadError, Notice, PageHeading, Skeleton, Submit, formatDate, useResource } from './ui';

const labels = { VIGENTE: 'Vigente', NO_VIGENTE: 'No vigente', NO_VERIFICABLE: 'No verificable', CONTINUADOR: 'Continuador', REINGRESANTE: 'Reingresante', NUEVO: 'Nuevo', ACEPTADA: 'Aceptada', RECIBIDA: 'Recibida' };
const label = value => labels[value] || value || 'Sin consultar';

export function SourceNotice({ source }) {
  return source === 'simulator' ? <Notice tone="warning"><strong>Entorno de simulación.</strong> Los datos hospitalarios son ejemplos de prueba. No representan una atención ni una reserva real.</Notice> : null;
}

export function EligibilityDetails({ eligibility, compact = false }) {
  if (!eligibility) return <p className="muted">Identifica al paciente y consulta la elegibilidad para ver esta información.</p>;
  const references = eligibility.referencias || [];
  const specialties = eligibility.especialidades || [];
  return <div className="stack">
    <div className="eligibility-heading"><ShieldCheck size={24} aria-hidden="true" /><div><h2>{eligibility.elegible ? 'Elegibilidad consultada' : 'Reserva no habilitada'}</h2><p className="muted">{eligibility.reserve_ready ? 'El resultado permite continuar al módulo de reserva cuando esté integrado.' : eligibility.elegible ? 'Revisa las condiciones pendientes antes de continuar.' : 'Revisa los motivos comunicados por el servicio.'}</p></div><Badge tone={eligibility.reserve_ready ? 'success' : 'warning'}>{eligibility.reserve_ready ? 'Habilitado' : 'Revisar condiciones'}</Badge></div>
    {(eligibility.reason_messages || []).map((reason, i) => <Notice key={reason.code || i} tone="warning">{reason.message}</Notice>)}
    <dl className="facts facts-grid"><div><dt>Estado SIS</dt><dd><Badge tone={eligibility.sis?.estado === 'VIGENTE' ? 'success' : 'warning'}>{label(eligibility.sis?.estado)}</Badge></dd></div><div><dt>Condición del paciente</dt><dd>{label(eligibility.condicion)}</dd></div><div><dt>Verificación SIS</dt><dd>{formatDate(eligibility.sis?.verificado_en, true)}</dd></div><div><dt>Próxima fecha para reservar</dt><dd>{eligibility.proxima_reserva_desde ? formatDate(eligibility.proxima_reserva_desde, true) : 'Sin espera informada'}</dd></div></dl>
    {!compact && <><section className="subsection"><h3>Referencias disponibles <span className="count">{references.length}</span></h3>{references.length ? <div className="reference-list">{references.map(ref => <article className="reference-item" key={ref.referencia_id}><div className="row-between"><h4>Referencia {ref.numero}</h4><Badge>{label(ref.estado)}</Badge></div><dl className="facts facts-grid"><div><dt>Establecimiento de origen</dt><dd>{ref.establecimiento_origen || 'No informado'}</dd></div><div><dt>Especialidad de destino</dt><dd>{ref.especialidad_destino?.nombre || 'No informada'}</dd></div><div><dt>Fecha de envío</dt><dd>{formatDate(ref.fecha_envio)}</dd></div><div><dt>Correspondencia para reserva</dt><dd>{ref.especialidades_coincidentes?.length ? 'Con especialidad hospitalaria asociada' : 'Sin correspondencia disponible'}</dd></div></dl></article>)}</div> : <p className="muted">El servicio no devolvió referencias disponibles.</p>}</section><section className="subsection"><h3>Especialidades informadas por el hospital</h3>{specialties.length ? <ul className="specialty-list">{specialties.map(item => <li key={item.especialidad_id}><span>{item.nombre}</span><span className="muted">{item.referencias?.length || 0} referencia(s) asociada(s)</span></li>)}</ul> : <p className="muted">No hay especialidades disponibles para este resultado.</p>}<p className="field-hint">La reserva depende también de la vigencia de la referencia y de la disponibilidad que consulte el módulo de citas.</p></section></>}
  </div>;
}

export function PatientDashboard({ user, navigate, revision }) {
  const { data, loading, error, reload } = useResource('/portal/dashboard', revision);
  useEffect(() => {
    if (!data?.identity?.expires_at) return;
    const timer = setTimeout(reload, Math.max(0, new Date(data.identity.expires_at).getTime() - Date.now()) + 100);
    return () => clearTimeout(timer);
  }, [data?.identity?.expires_at, reload]);
  if (loading) return <Skeleton />;
  if (error) return <LoadError error={error} retry={reload} />;
  const appointment = data.next_appointment;
  return <><PageHeading title={`Hola, ${user.name}`}>Este es el resumen de tu cuenta y de la última consulta hospitalaria.</PageHeading><SourceNotice source={data.source} />
    {!data.identity?.identified && <section className="start-panel"><div className="start-symbol"><ClipboardCheck size={27} aria-hidden="true" /></div><div><h2>Comienza identificando al paciente</h2><p>Consulta el SIS, las referencias y las especialidades usando DNI y fecha de nacimiento.</p></div><button className="button primary" onClick={() => navigate('identify')}>Identificar paciente<ArrowRight size={17} aria-hidden="true" /></button></section>}
    {data.identity?.identified && <section className="panel"><div className="section-heading"><h2>Tu elegibilidad</h2><button className="text-button" onClick={() => navigate('identify')}>Ver detalle<ArrowRight size={16} aria-hidden="true" /></button></div><EligibilityDetails eligibility={data.eligibility} compact /></section>}
    <div className="dashboard-columns"><section className="panel"><h2><CalendarDays size={20} aria-hidden="true" />Próxima cita</h2>{appointment ? <><div className="appointment-date">{formatDate(appointment.fecha)} <span>{appointment.hora_inicio}</span></div><h3>{appointment.especialidad}</h3><dl className="facts"><div><dt>Consultorio</dt><dd>{appointment.consultorio}</dd></div><div><dt>Médico</dt><dd>{appointment.medico}</dd></div><div><dt>Código</dt><dd>{appointment.codigo_cita}</dd></div><div><dt>Estado</dt><dd>{appointment.estado}</dd></div></dl>{appointment.indicaciones?.length > 0 && <ul className="plain-list">{appointment.indicaciones.map((text, index) => <li key={index}>{text}</li>)}</ul>}</> : <div className="empty-state"><p>{data.appointments_status === 'identity_required' ? 'Primero identifica al paciente.' : data.appointments_status === 'unavailable' ? 'No se pudo consultar la próxima cita.' : 'No se encontraron próximas citas.'}</p><span className="muted">La reserva y la gestión de citas se incorporan con los módulos del equipo.</span></div>}</section>
      <section className="panel"><h2>Notificaciones</h2>{data.notifications?.integrated ? data.notifications.items?.length ? <ul className="plain-list">{data.notifications.items.map((item, i) => <li key={item.id || i}>{item.message || item.title}</li>)}</ul> : <p className="muted">No tienes notificaciones nuevas.</p> : <div className="empty-state"><Badge>Sin integrar</Badge><p>El resumen estará disponible al conectar el módulo de notificaciones.</p></div>}<div className="subsection"><h3>Tu opinión cuenta</h3><p className="muted">Comparte tu experiencia después de consultar la elegibilidad.</p><button className="text-button" onClick={() => navigate('surveys')}>{data.survey?.submitted ? 'Ver estado de la encuesta' : 'Ir a satisfacción'}<ArrowRight size={16} aria-hidden="true" /></button></div></section></div>
    {data.integration_errors?.map((item, i) => <Notice key={i} tone="warning">{typeof item === 'string' ? item : item.message || 'Hay un servicio temporalmente no disponible.'}</Notice>)}
  </>;
}

export function Identification({ onChanged, revision }) {
  const initial = useResource('/portal/dashboard', revision);
  const policies = useResource('/portal/policies');
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
    try { const data = await api('/portal/eligibility?refresh=true'); setEligibility(data.eligibility); setIdentity(data.identity); setSource(data.source); onChanged(); }
    catch (e) { setError(e.message); if (e.status === 401 || e.status === 410) { setIdentity(null); setEligibility(null); } }
    finally { setBusy(false); }
  }
  async function identify(e) {
    e.preventDefault(); setBusy(true); setError(''); setMessage('');
    try {
      const data = await api('/portal/identify', { method: 'POST', body: { ...form, ...challenge } });
      setIdentity(data.identity); setEligibility(null); setSource(data.source);
      setForm({ numero_documento: '', fecha_nacimiento: '', consent: false });
      try { const evaluated = await api('/portal/eligibility'); setEligibility(evaluated.eligibility); setIdentity(evaluated.identity); }
      catch (e) { setError(e.message); if (e.status === 401 || e.status === 410) setIdentity(null); }
      onChanged();
    } catch (e) { setError(e.message); }
    finally { setBusy(false); setChallengeRevision(v => v + 1); }
  }
  async function clearIdentity() {
    setBusy(true); setError('');
    try { await api('/portal/identity', { method: 'DELETE' }); setIdentity(null); setEligibility(null); setMessage('Identificación cerrada. Puedes consultar a otro paciente.'); onChanged(); }
    catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  const [today] = useState(() => new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Lima', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date()));
  return <><PageHeading title="Identificación y elegibilidad">Consulta las condiciones para acceder a una reserva en línea.</PageHeading><SourceNotice source={source || policies.data?.source} /><Notice tone="error" focus>{error}</Notice><Notice tone="success" focus>{message}</Notice>
    {initial.loading ? <Skeleton /> : initial.error ? <LoadError error={initial.error} retry={initial.reload} /> : identity?.identified ? <><section className="identity-bar"><div><strong>{identity.paciente?.nombre_enmascarado || 'Paciente identificado'}</strong><span>{identity.paciente?.edad != null ? `${identity.paciente.edad} años · ` : ''}Identificación vigente por {Math.floor(remaining / 60)}:{String(remaining % 60).padStart(2, '0')}</span></div><button className="button secondary" disabled={busy} onClick={clearIdentity}>Cambiar paciente</button></section><section className="panel"><div className="section-heading"><h2>Resultado de la consulta</h2><button className="text-button" disabled={busy} onClick={queryEligibility}><RefreshCw size={16} className={busy ? 'spin' : ''} aria-hidden="true" />{busy ? 'Consultando…' : 'Actualizar'}</button></div><EligibilityDetails eligibility={eligibility} />{!eligibility && !busy && <button className="button primary" onClick={queryEligibility}>Consultar elegibilidad</button>}</section><Notice>La selección de cupos y la creación de citas se habilitarán al integrar el módulo de reservas. Esta consulta no crea una cita.</Notice></> : <div className="detail-layout"><section className="panel"><h2>Datos del paciente</h2><form className="stack" onSubmit={identify}><Field label="DNI" type="text" inputMode="numeric" autoComplete="off" pattern="[0-9]{8}" maxLength={8} minLength={8} value={form.numero_documento} onChange={e => setForm(v => ({ ...v, numero_documento: e.target.value.replace(/\D/g, '') }))} hint="Ingresa los 8 dígitos del documento." required /><Field label="Fecha de nacimiento" type="date" autoComplete="off" max={today} value={form.fecha_nacimiento} onChange={e => setForm(v => ({ ...v, fecha_nacimiento: e.target.value }))} required />
      {policies.loading ? <Skeleton label="Cargando aviso de privacidad" /> : policies.error ? <LoadError error={policies.error} retry={policies.reload} /> : <><div className="privacy-text"><h3>Antes de consultar</h3><p>{policies.data?.privacy_notice || 'El DNI y la fecha de nacimiento se utilizan únicamente para identificar al paciente durante esta sesión.'}</p>{!policies.data?.privacy_approved && <p className="field-hint">Aviso provisional para el prototipo. Utiliza únicamente datos de prueba mientras no exista aprobación institucional.</p>}</div><label className="check-row"><input type="checkbox" checked={form.consent} onChange={e => setForm(v => ({ ...v, consent: e.target.checked }))} required /><span>He leído el aviso y autorizo la consulta de los datos del paciente.</span></label></>}
      <Challenge value={challenge} onChange={setChallenge} refreshKey={challengeRevision} purpose="consultar al paciente" /><div><Submit busy={busy} disabled={busy || !challenge.challenge_id || !policies.data || !form.consent}>Identificar y consultar</Submit></div></form></section><aside className="context-panel"><h2>Qué podrás consultar</h2><ul className="plain-list"><li>Estado de afiliación al SIS.</li><li>Condición del paciente.</li><li>Referencias y especialidades disponibles.</li><li>Próxima fecha permitida para reservar.</li></ul><p className="muted">Crear una cuenta no registra al paciente en el hospital ni garantiza su elegibilidad. El resultado depende del servicio hospitalario.</p></aside></div>}
  </>;
}

function Rating({ name, legend, value, onChange, low, high }) {
  return <fieldset className="rating"><legend>{legend}</legend><div className="rating-options">{[1, 2, 3, 4, 5].map(score => <label key={score} className={value === score ? 'selected' : ''}><input type="radio" name={name} value={score} checked={value === score} onChange={() => onChange(score)} required /><span>{score}</span></label>)}</div><div className="rating-labels"><span>1 · {low}</span><span>5 · {high}</span></div></fieldset>;
}
export function Surveys({ navigate, onChanged }) {
  const { data, loading, error: loadError, reload } = useResource('/portal/surveys/status');
  const [form, setForm] = useState({ ease_score: null, satisfaction_score: null, comment: '' });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  async function submit(e) {
    e.preventDefault(); setBusy(true); setError('');
    try { const result = await api('/portal/surveys', { method: 'POST', body: form }); setMessage(result.message || 'Gracias. Tu respuesta fue guardada.'); onChanged(); reload(); }
    catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  return <><PageHeading title="Tu experiencia">Ayúdanos a mejorar la facilidad de uso del portal.</PageHeading><Notice tone="error" focus>{error}</Notice><Notice tone="success" focus>{message}</Notice>{loading ? <Skeleton /> : loadError ? <LoadError error={loadError} retry={reload} /> : data.submitted ? <section className="panel form-panel"><h2>Gracias por compartir tu opinión</h2><p>Ya registraste una respuesta para esta consulta. Tus valoraciones se incluyen en las estadísticas de satisfacción.</p><button className="button secondary" onClick={() => navigate('dashboard')}>Volver al inicio</button></section> : !data.eligible ? <section className="panel form-panel"><h2>Primero utiliza el portal</h2><p>La encuesta se habilita al completar una consulta de elegibilidad. Se admite una respuesta por consulta habilitada.</p><button className="button primary" onClick={() => navigate('identify')}>Consultar elegibilidad<ArrowRight size={17} aria-hidden="true" /></button></section> : <section className="panel form-panel"><h2>¿Cómo fue tu experiencia?</h2><p className="muted">Escala de 1 a 5 configurada para este prototipo. No incluyas DNI, diagnósticos ni información clínica en tu comentario.</p><form className="stack" onSubmit={submit}><Rating name="ease" legend="¿Qué tan fácil fue utilizar el sistema?" value={form.ease_score} onChange={value => setForm(v => ({ ...v, ease_score: value }))} low="Muy difícil" high="Muy fácil" /><Rating name="satisfaction" legend="¿Qué tan satisfecho estás con la experiencia?" value={form.satisfaction_score} onChange={value => setForm(v => ({ ...v, satisfaction_score: value }))} low="Nada satisfecho" high="Muy satisfecho" /><div className="field"><label htmlFor="survey-comment">Comentario <span className="muted">(opcional)</span></label><textarea id="survey-comment" maxLength={1000} rows={4} value={form.comment} onChange={e => setForm(v => ({ ...v, comment: e.target.value }))} /><span className="field-hint">{form.comment.length}/1000 caracteres</span></div><div><Submit busy={busy}>Enviar mi opinión</Submit></div></form></section>}</>;
}
