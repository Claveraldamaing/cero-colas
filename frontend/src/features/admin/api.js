import { api } from '../../shared/api/client';

export const adminDashboardPath = '/portal/admin/dashboard';
export const usersPath = (offset, query) => `/admin/users?limit=20&offset=${offset}&q=${encodeURIComponent(query)}`;

export const getAdminDashboard = () => api(adminDashboardPath);
export const listUsers = (offset, query) => api(usersPath(offset, query));
export const updateUser = (id, body) => api(`/admin/users/${id}`, { method: 'PATCH', body });
