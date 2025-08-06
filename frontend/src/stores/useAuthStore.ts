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
  dailyLimit: number; // 추가: 일일 제한량
  isUsageLimitReached: boolean; // 추가: 제한 도달 상태
  setUser: (user: User | null) => void;
  setLoading: (loading: boolean) => void;
  setRemainingUsage: (usage: number) => void;
  setDailyLimit: (limit: number) => void; // 추가
  setUsageLimitReached: (reached: boolean) => void; // 추가
  logout: () => void;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  isAuthenticated: false,
  isLoading: true,
  remainingUsage: 0, // 하드코딩 제거 (0으로 초기화, 백엔드에서 가져올 때까지)
  dailyLimit: 5, // 추가: 기본값 5
  isUsageLimitReached: false, // 추가: 초기값 false
  
  setUser: (user) => set({ user, isAuthenticated: !!user }),
  
  setLoading: (isLoading) => set({ isLoading }),
  
  setRemainingUsage: (remainingUsage) => {
    const { dailyLimit } = get();
    set({ 
      remainingUsage,
      isUsageLimitReached: remainingUsage <= 0 // 제한 도달 상태 자동 업데이트
    });
  },
  
  setDailyLimit: (dailyLimit) => {
    const { remainingUsage } = get();
    set({ 
      dailyLimit,
      isUsageLimitReached: remainingUsage <= 0 // 제한 도달 상태 자동 업데이트
    });
  },
  
  setUsageLimitReached: (isUsageLimitReached) => set({ isUsageLimitReached }),
  
  logout: () => set({ 
    user: null, 
    isAuthenticated: false, 
    remainingUsage: 0, // 로그아웃 시 0으로 리셋
    isUsageLimitReached: false // 로그아웃 시 제한 상태 리셋
  })
}));