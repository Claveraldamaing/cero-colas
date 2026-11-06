import { useState } from 'react';
import { Notice, PageHeading, Submit } from '../../shared/ui';
import { formatDate } from '../../shared/lib/date';
import { bookAppointment, getAvailability, getSlots } from './api';

const steps = ['Especialidad', 'Fecha', 'Horario', 'Confirmación'];

function getPreviewDate() {
  const date = new Date();
  date.setDate(date.getDate() + 1);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

function StepList({ active }) {
  return <ol className="reservation-steps" aria-label="Pasos de la reserva">
    {steps.map((label, index) => <li key={label} className={index === active ? 'active' : index < active ? 'complete' : ''}>
      <span>{index < active ? '✓' : index + 1}</span>{label}
    </li>)}
  </ol>;
}

export default function ReservationWizard({ eligibility, onExit }) {
  const previewMode = !eligibility?.reserve_ready;
  const [step, setStep] = useState(0);
  const [specialty, setSpecialty] = useState(null);
  const [referenceId, setReferenceId] = useState('');
  const [month, setMonth] = useState(() => new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Lima', year: 'numeric', month: '2-digit' }).format(new Date()));
  const [days, setDays] = useState([]);
  const [selectedDate, setSelectedDate] = useState('');
  const [slots, setSlots] = useState([]);
  const [selectedSlot, setSelectedSlot] = useState(null);
  const [phone, setPhone] = useState('');
  const [receipt, setReceipt] = useState(null);
  const [idempotencyKey] = useState(() => crypto.randomUUID());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [copyMessage, setCopyMessage] = useState('');
  const specialties = eligibility?.specialties_allowed || [];
  const previewSpecialties = specialties.length
    ? specialties
    : [{ especialidad_id: 'preview-specialty', nombre: 'Especialidad de ejemplo', referencias: ['preview-reference'] }];

  async function loadDays(event) {
    event.preventDefault();
    setError('');
    if (previewMode) {
      setDays([{ date: getPreviewDate(), available_slots: 2 }]);
      setSelectedDate('');
      setSlots([]);
      setSelectedSlot(null);
      return;
    }
    setBusy(true);
    try {
      const result = await getAvailability(specialty.especialidad_id, month);
      setDays(result.items);
      setSelectedDate('');
      setSlots([]);
      setSelectedSlot(null);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  }

  async function loadSlots() {
    setError('');
    if (previewMode) {
      setSlots([
        { slot_id: 'preview-slot-1', date: selectedDate, start_time: '09:00', end_time: '09:30', doctor: 'Profesional de ejemplo', office: 'Consultorio de ejemplo' },
        { slot_id: 'preview-slot-2', date: selectedDate, start_time: '10:00', end_time: '10:30', doctor: 'Profesional de ejemplo', office: 'Consultorio de ejemplo' },
      ]);
      setSelectedSlot(null);
      setStep(2);
      return;
    }
    setBusy(true);
    try {
      const result = await getSlots(specialty.especialidad_id, selectedDate);
      setSlots(result.items);
      setSelectedSlot(null);
      setStep(2);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  }

  async function confirm(event) {
    event.preventDefault();
    if (previewMode) return;
    setError('');
    setBusy(true);
    try {
      const result = await bookAppointment({
        specialty_id: specialty.especialidad_id,
        slot_id: selectedSlot.slot_id,
        reference_id: referenceId,
        contact_phone: phone,
        idempotency_key: idempotencyKey,
      });
      setReceipt(result);
      setStep(4);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  }

  async function copyCancellationKey() {
    setCopyMessage('');
    try {
      await navigator.clipboard.writeText(receipt.clave_anulacion);
      setCopyMessage('Clave copiada.');
    } catch {
      setCopyMessage('No se pudo copiar. Anótala manualmente.');
    }
  }

  if (step === 4 && receipt) {
    const appointment = receipt.cita;
    return <div className="stack">
      <PageHeading title="¡Cita reservada!">La confirmación fue recibida del servicio hospitalario.</PageHeading>
      <Notice tone="success">Código de cita: <strong>{appointment.codigo_cita}</strong></Notice>
      {receipt.clave_anulacion && <section className="panel cancellation-key">
        <h2>Clave de anulación</h2>
        <output>{receipt.clave_anulacion}</output>
        <p className="muted">Guárdala en un lugar seguro. La necesitarás para anular la cita.</p>
        <button className="button secondary" onClick={copyCancellationKey}>Copiar clave</button>
        <span role="status">{copyMessage}</span>
      </section>}
      <section className="panel stack">
        <h2>Resumen de la cita</h2>
        <p><strong>Especialidad:</strong> {appointment.especialidad}</p>
        <p><strong>Fecha:</strong> {formatDate(appointment.fecha)}</p>
        <p><strong>Hora:</strong> {appointment.hora_inicio}{appointment.hora_fin ? `–${appointment.hora_fin}` : ''}</p>
        <p><strong>Médico:</strong> {appointment.medico || 'No informado'}</p>
        <p><strong>Consultorio:</strong> {appointment.consultorio || 'No informado'}</p>
        {appointment.indicaciones?.length > 0 && <div><h3>Indicaciones</h3><ul>{appointment.indicaciones.map((item, index) => <li key={`${index}-${item}`}>{item}</li>)}</ul></div>}
      </section>
      <button className="button primary" onClick={onExit}>Volver al portal</button>
    </div>;
  }

  return <div className="stack">
    <PageHeading title="Reserva de cita">Sigue los pasos para elegir un horario y confirmar tu cita.</PageHeading>
    <StepList active={step} />
    {previewMode
      ? <Notice tone="warning"><strong>Vista previa:</strong> las fechas y horarios son ejemplos. No se consulta disponibilidad del hospital y no se puede crear una cita.</Notice>
      : eligibility?.reservation_simulation
        ? <Notice tone="warning"><strong>Reserva de prueba:</strong> la solicitud se envía al simulador local. No crea una cita real en el hospital.</Notice>
        : <Notice>Tu identificación hospitalaria se conserva solo en esta sesión. La cita se confirma con el servicio del hospital.</Notice>}
    <Notice tone="error" focus>{error}</Notice>

    {step === 0 && <section className="panel stack">
      <h2>1. Selecciona una especialidad</h2>
      {(previewMode ? previewSpecialties : specialties).map(item => <button key={item.especialidad_id} className={`reservation-option ${specialty?.especialidad_id === item.especialidad_id ? 'selected' : ''}`} aria-pressed={specialty?.especialidad_id === item.especialidad_id} onClick={() => {
        setSpecialty(item);
        setReferenceId(item.referencias?.[0] || '');
      }}>
        <strong>{item.nombre}</strong><span>{previewMode ? 'Ejemplo; no disponible para reservar' : `${item.referencias?.length || 0} referencia(s) habilitada(s)`}</span>
      </button>)}
      {!specialties.length && !previewMode && <p className="muted">No hay especialidades habilitadas para las referencias vigentes.</p>}
      {specialty?.referencias?.length > 1 && <label className="field">Referencia
        <select value={referenceId} onChange={event => setReferenceId(event.target.value)}>
          {specialty.referencias.map((id, index) => <option key={id} value={id}>Referencia {index + 1}</option>)}
        </select>
      </label>}
      <div className="reservation-actions">
        <button className="button secondary" onClick={onExit}>Volver</button>
        <button className="button primary" disabled={!specialty || !referenceId} onClick={() => setStep(1)}>Continuar</button>
      </div>
    </section>}

    {step === 1 && <section className="panel stack">
      <h2>2. Selecciona una fecha</h2>
      <form className="reservation-actions" onSubmit={loadDays}>
        <label className="field">Mes de atención
          <input type="month" value={month} onChange={event => { setMonth(event.target.value); setDays([]); setSelectedDate(''); }} required />
        </label>
        <button className="button primary" type="submit" disabled={busy}>{busy ? 'Consultando…' : previewMode ? 'Ver fecha de ejemplo' : 'Consultar fechas'}</button>
      </form>
      <div className="reservation-day-list">{days.map(day => <button key={day.date} className={`reservation-option ${selectedDate === day.date ? 'selected' : ''}`} disabled={!day.available_slots || busy} aria-pressed={selectedDate === day.date} onClick={() => setSelectedDate(day.date)}>
        <strong>{formatDate(day.date)}</strong><span>{day.available_slots} cupo(s)</span>
      </button>)}</div>
      {days.length === 0 && <p className="muted">{previewMode ? 'Muestra un día de ejemplo para recorrer el paso.' : 'Consulta un mes para ver los días con disponibilidad.'}</p>}
      <div className="reservation-actions">
        <button className="button secondary" disabled={busy} onClick={() => setStep(0)}>Volver</button>
        <button className="button primary" disabled={!selectedDate || busy} onClick={loadSlots}>{busy ? 'Buscando horarios…' : 'Ver horarios'}</button>
      </div>
    </section>}

    {step === 2 && <section className="panel stack">
      <h2>3. Selecciona un horario</h2>
      <p>{formatDate(selectedDate)}</p>
      {slots.map(slot => <button key={slot.slot_id} className={`reservation-option ${selectedSlot?.slot_id === slot.slot_id ? 'selected' : ''}`} aria-pressed={selectedSlot?.slot_id === slot.slot_id} onClick={() => setSelectedSlot(slot)}>
        <strong>{slot.start_time}–{slot.end_time}</strong><span>{slot.doctor} · {slot.office}</span>
      </button>)}
      {!slots.length && <p className="muted">{previewMode ? 'No hay horarios de ejemplo para esta fecha.' : 'No quedan horarios para esta fecha. Vuelve y elige otro día.'}</p>}
      <div className="reservation-actions">
        <button className="button secondary" onClick={() => setStep(1)}>Volver a fechas</button>
        <button className="button primary" disabled={!selectedSlot} onClick={() => setStep(3)}>Continuar</button>
      </div>
    </section>}

    {step === 3 && <section className="panel stack">
      <h2>4. Confirma los datos</h2>
      <div className="facts facts-grid">
        <div><dt>Especialidad</dt><dd>{specialty.nombre}</dd></div>
        <div><dt>Fecha</dt><dd>{formatDate(selectedSlot.date)}</dd></div>
        <div><dt>Horario</dt><dd>{selectedSlot.start_time}–{selectedSlot.end_time}</dd></div>
        <div><dt>Médico</dt><dd>{selectedSlot.doctor}</dd></div>
        <div><dt>Consultorio</dt><dd>{selectedSlot.office}</dd></div>
      </div>
      {previewMode
        ? <Notice tone="warning">En el flujo real, aquí se revisarían tus datos y se enviaría la solicitud al hospital. La confirmación está deshabilitada hasta configurar los requisitos.</Notice>
        : <form className="stack" onSubmit={confirm}>
        <label className="field">Teléfono de contacto
          <input type="tel" inputMode="numeric" autoComplete="tel" pattern="([0-9]{7}|[0-9]{9})" maxLength={9} value={phone} onChange={event => setPhone(event.target.value.replace(/\D/g, ''))} required />
          <span className="field-hint">Ingresa 7 dígitos para teléfono fijo o 9 para celular.</span>
        </label>
        <Notice tone="warning">{eligibility?.reservation_simulation ? 'Al confirmar, se creará una cita de prueba en el simulador local; no es una reserva real.' : 'Al confirmar, se realizará la reserva en el servicio hospitalario. Verifica fecha y horario antes de continuar.'}</Notice>
        <div className="reservation-actions">
          <button className="button secondary" type="button" disabled={busy} onClick={() => setStep(2)}>Volver</button>
          <Submit busy={busy} disabled={busy || ![7, 9].includes(phone.length)}>Confirmar cita</Submit>
        </div>
      </form>}
      {previewMode && <div className="reservation-actions">
        <button className="button secondary" onClick={() => setStep(2)}>Volver</button>
        <button className="button primary" disabled title="La confirmación se habilitará cuando se configuren y cumplan los requisitos">Confirmación no disponible</button>
      </div>}
    </section>}
  </div>;
}
