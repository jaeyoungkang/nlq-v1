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
  dailyLimit: number;
  isUsageLimitReached: boolean;
  setUser: (user: User | null) => void;
  setLoading: (loading: boolean) => void;
  setRemainingUsage: (usage: number) => void;
  setDailyLimit: (limit: number) => void;
  setUsageLimitReached: (reached: boolean) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  isAuthenticated: false,
  isLoading: true,
  remainingUsage: 0, // 백엔드에서 받을 때까지 0으로 초기화
  dailyLimit: 0, // 백엔드에서 받을 때까지 0으로 초기화 (하드코딩 제거)
  isUsageLimitReached: false,
  
  setUser: (user) => set({ user, isAuthenticated: !!user }),
  
  setLoading: (isLoading) => set({ isLoading }),
  
  setRemainingUsage: (remainingUsage) => {
    const { dailyLimit } = get();
    set({ 
      remainingUsage,
      isUsageLimitReached: remainingUsage <= 0
    });
  },
  
  setDailyLimit: (dailyLimit) => {
    const { remainingUsage } = get();
    set({ 
      dailyLimit,
      isUsageLimitReached: remainingUsage <= 0
    });
  },
  
  setUsageLimitReached: (isUsageLimitReached) => set({ isUsageLimitReached }),
  
  logout: () => set({ 
    user: null, 
    isAuthenticated: false, 
    remainingUsage: 0,
    dailyLimit: 0, // 로그아웃 시 0으로 리셋
    isUsageLimitReached: false
  })
}));