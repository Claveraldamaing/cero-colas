import { api } from '../../shared/api/client';

export const getAvailability = (specialtyId, month) => api(
  `/reservations/availability?specialty_id=${encodeURIComponent(specialtyId)}&month=${encodeURIComponent(month)}`,
);

export const getSlots = (specialtyId, date) => api(
  `/reservations/slots?specialty_id=${encodeURIComponent(specialtyId)}&date=${encodeURIComponent(date)}`,
);

export const bookAppointment = body => api('/reservations', { method: 'POST', body });
