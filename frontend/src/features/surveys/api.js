import { api } from '../../shared/api/client';

export const surveyStatusPath = '/portal/surveys/status';

export const getSurveyStatus = () => api(surveyStatusPath);
export const submitSurvey = body => api('/portal/surveys', { method: 'POST', body });
