import { useState } from 'react';
import { ArrowRight } from 'lucide-react';
import { LoadError, Notice, PageHeading, Skeleton, Submit } from '../../shared/ui';
import { useResource } from '../../shared/hooks/useResource';
import { submitSurvey, surveyStatusPath } from './api';
import Rating from './components/Rating';

export default function SurveysPage({ navigate, onChanged }) {
  const { data, loading, error: loadError, reload } = useResource(surveyStatusPath);
  const [form, setForm] = useState({ ease_score: null, satisfaction_score: null, comment: '' });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  async function submit(e) {
    e.preventDefault(); setBusy(true); setError('');
    try { const result = await submitSurvey(form); setMessage(result.message || 'Gracias. Tu respuesta fue guardada.'); onChanged(); reload(); }
    catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  return <><PageHeading title="Tu experiencia">Ayúdanos a mejorar la facilidad de uso del portal.</PageHeading><Notice tone="error" focus>{error}</Notice><Notice tone="success" focus>{message}</Notice>{loading ? <Skeleton /> : loadError ? <LoadError error={loadError} retry={reload} /> : data.submitted ? <section className="panel form-panel"><h2>Gracias por compartir tu opinión</h2><p>Ya registraste una respuesta para esta consulta. Tus valoraciones se incluyen en las estadísticas de satisfacción.</p><button className="button secondary" onClick={() => navigate('dashboard')}>Volver al inicio</button></section> : !data.eligible ? <section className="panel form-panel"><h2>Primero utiliza el portal</h2><p>La encuesta se habilita al completar una consulta de elegibilidad. Se admite una respuesta por consulta habilitada.</p><button className="button primary" onClick={() => navigate('identify')}>Consultar elegibilidad<ArrowRight size={17} aria-hidden="true" /></button></section> : <section className="panel form-panel"><h2>¿Cómo fue tu experiencia?</h2><p className="muted">Escala de 1 a 5 configurada para este prototipo. No incluyas DNI, diagnósticos ni información clínica en tu comentario.</p><form className="stack" onSubmit={submit}><Rating name="ease" legend="¿Qué tan fácil fue utilizar el sistema?" value={form.ease_score} onChange={value => setForm(v => ({ ...v, ease_score: value }))} low="Muy difícil" high="Muy fácil" /><Rating name="satisfaction" legend="¿Qué tan satisfecho estás con la experiencia?" value={form.satisfaction_score} onChange={value => setForm(v => ({ ...v, satisfaction_score: value }))} low="Nada satisfecho" high="Muy satisfecho" /><div className="field"><label htmlFor="survey-comment">Comentario <span className="muted">(opcional)</span></label><textarea id="survey-comment" maxLength={1000} rows={4} value={form.comment} onChange={e => setForm(v => ({ ...v, comment: e.target.value }))} /><span className="field-hint">{form.comment.length}/1000 caracteres</span></div><div><Submit busy={busy}>Enviar mi opinión</Submit></div></form></section>}</>;
}
