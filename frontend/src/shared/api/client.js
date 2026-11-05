// Session and CSRF values live only in memory. Hospital tokens never reach this client.
let csrfToken = null;
let onExpired = () => {};
export function setCsrf(value) { csrfToken = value || null; }
export function setSessionExpiredHandler(handler) { onExpired = handler; }
export class ApiError extends Error {
  constructor(message, status, code) { super(message); this.status = status; this.code = code; }
}
export async function api(path, { method = 'GET', body, signal, silentUnauthorized = false } = {}) {
  let response;
  try {
    response = await fetch(`/api/v1${path}`, {
      method, credentials: 'include', signal,
      headers: { Accept: 'application/json', ...(body ? { 'Content-Type': 'application/json' } : {}),
        ...(csrfToken && method !== 'GET' ? { 'X-CSRF-Token': csrfToken } : {}) },
      ...(body ? { body: JSON.stringify(body) } : {}),
    });
  } catch (error) {
    if (error.name === 'AbortError') throw error;
    throw new ApiError('No se pudo conectar con el servicio. Comprueba tu conexión y vuelve a intentarlo.', 0, 'NETWORK_ERROR');
  }
  let data;
  try { data = await response.json(); } catch { data = null; }
  if (!response.ok) {
    const detail = data?.detail;
    const message = typeof detail === 'string' ? detail : Array.isArray(detail)
      ? detail.map(item => `${item.loc?.at(-1) || 'Dato'}: ${item.msg}`).join('. ')
      : detail?.message || data?.message || 'No se pudo completar la solicitud. Vuelve a intentarlo.';
    if (response.status === 401 && !silentUnauthorized && (!path.startsWith('/portal/') || ['AUTH_REQUIRED', 'SESSION_EXPIRED', 'ACCOUNT_UNAVAILABLE'].includes(detail?.code))) onExpired();
    const tracking = detail?.rastreo ? ` Código de rastreo: ${detail.rastreo}.` : '';
    const retry = detail?.retry_after ? ` Vuelve a intentarlo en ${detail.retry_after} segundos.` : '';
    throw new ApiError(message + tracking + retry, response.status, detail?.code || 'REQUEST_FAILED');
  }
  if (data?.csrf_token) setCsrf(data.csrf_token);
  return data;
}
