import { ClipboardCheck, Home, LayoutDashboard, MessageSquare, Settings2, ShieldCheck, UserRound, Users } from 'lucide-react';

export function navigationFor(user) {
  return [
    ...(user.role === 'ADMIN' ? [['admin', 'Resumen general', LayoutDashboard], ['users', 'Usuarios', Users]] : []),
    ['dashboard', 'Mi inicio', Home], ['identify', 'Identificación', ClipboardCheck], ['surveys', 'Satisfacción', MessageSquare],
    ['profile', 'Mi perfil', UserRound], ['security', 'Seguridad', ShieldCheck], ['preferences', 'Preferencias', Settings2],
  ];
}
