import { api } from '../../shared/api/client';

export const updateProfile = body => api('/auth/profile', { method: 'PATCH', body });
export const changePassword = body => api('/auth/change-password', { method: 'POST', body });
