import { Notice } from './index';

export function SourceNotice({ source }) {
  return source === 'simulator' ? <Notice tone="warning"><strong>Entorno de simulación.</strong> Los datos hospitalarios son ejemplos de prueba. No representan una atención ni una reserva real.</Notice> : null;
}
