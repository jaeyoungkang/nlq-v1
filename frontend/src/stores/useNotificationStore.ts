// frontend/src/stores/useNotificationStore.ts

import { create } from 'zustand';

interface NotificationState {
  message: string | null;
  type: 'error' | 'success' | 'info';
  setMessage: (message: string, type: 'error' | 'success' | 'info') => void;
  clearMessage: () => void;
}

export const useNotificationStore = create<NotificationState>((set) => ({
  message: null,
  type: 'info',
  setMessage: (message, type) => set({ message, type }),
  clearMessage: () => set({ message: null }),
}));