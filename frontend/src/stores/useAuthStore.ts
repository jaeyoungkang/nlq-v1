import { create } from 'zustand';

export interface User {
  user_id: string;
  email: string;
  name: string;
  picture: string;
}

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  remainingUsage: number;
  setUser: (user: User | null) => void;
  setLoading: (loading: boolean) => void;
  setRemainingUsage: (usage: number) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isAuthenticated: false,
  isLoading: true,
  remainingUsage: 10,
  setUser: (user) => set({ user, isAuthenticated: !!user }),
  setLoading: (isLoading) => set({ isLoading }),
  setRemainingUsage: (remainingUsage) => set({ remainingUsage }),
  logout: () => set({ user: null, isAuthenticated: false, remainingUsage: 10 })
}));