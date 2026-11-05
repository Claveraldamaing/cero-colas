import { ShieldCheck } from 'lucide-react';
import { Badge, Notice } from '../../../shared/ui';
import { formatDate } from '../../../shared/lib/date';

const labels = { VIGENTE: 'Vigente', NO_VIGENTE: 'No vigente', NO_VERIFICABLE: 'No verificable', CONTINUADOR: 'Continuador', REINGRESANTE: 'Reingresante', NUEVO: 'Nuevo', ACEPTADA: 'Aceptada', RECIBIDA: 'Recibida' };
const label = value => labels[value] || value || 'Sin consultar';

export default function EligibilityDetails({ eligibility, compact = false }) {
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
