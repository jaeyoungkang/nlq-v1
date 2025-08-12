import { create } from 'zustand';

export interface User {
  user_id: string;
  email: string;
  name: string;
  picture: string;
}

export interface WhitelistError {
  message: string;
  errorType: string;
  reason?: string;
  userStatus?: string;
}

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  whitelistError: WhitelistError | null;
  setUser: (user: User | null) => void;
  setLoading: (loading: boolean) => void;
  setWhitelistError: (error: WhitelistError | null) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isAuthenticated: false,
  isLoading: true,
  whitelistError: null,
  
  setUser: (user) => set({ user, isAuthenticated: !!user }),
  
  setLoading: (isLoading) => set({ isLoading }),
  
  setWhitelistError: (whitelistError) => set({ whitelistError }),
  
  logout: () => set({ 
    user: null, 
    isAuthenticated: false,
    whitelistError: null
  })
}));