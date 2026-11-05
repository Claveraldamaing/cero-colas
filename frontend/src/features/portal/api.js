import { api } from '../../shared/api/client';

export const portalPaths = {
  dashboard: '/portal/dashboard',
  policies: '/portal/policies',
};

export const getDashboard = () => api(portalPaths.dashboard);
export const getPolicies = () => api(portalPaths.policies);
export const identifyPatient = body => api('/portal/identify', { method: 'POST', body });
export const getEligibility = (refresh = false) => api(`/portal/eligibility${refresh ? '?refresh=true' : ''}`);
export const clearIdentity = () => api('/portal/identity', { method: 'DELETE' });
