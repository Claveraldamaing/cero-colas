import { api } from '../../shared/api/client';

export const getSession = options => api('/auth/me', { silentUnauthorized: true, ...options });
export const logout = () => api('/auth/logout', { method: 'POST' });
export const login = body => api('/auth/login', { method: 'POST', body, silentUnauthorized: true });
export const register = body => api('/auth/register', { method: 'POST', body, silentUnauthorized: true });
export const forgotPassword = body => api('/auth/forgot-password', { method: 'POST', body, silentUnauthorized: true });
export const resetPassword = body => api('/auth/reset-password', { method: 'POST', body, silentUnauthorized: true });
