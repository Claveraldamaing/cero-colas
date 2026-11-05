import { useEffect } from 'react';
import { ArrowRight, CalendarDays, ClipboardCheck } from 'lucide-react';
import { Badge, LoadError, Notice, PageHeading, Skeleton } from '../../shared/ui';
import { SourceNotice } from '../../shared/ui/SourceNotice';
import { useResource } from '../../shared/hooks/useResource';
import { formatDate } from '../../shared/lib/date';
import { portalPaths } from './api';
import EligibilityDetails from './components/EligibilityDetails';

export default function DashboardPage({ user, navigate, revision }) {
  const { data, loading, error, reload } = useResource(portalPaths.dashboard, revision);
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
