'use client';

import { LogOut } from 'lucide-react';
import { useAuth } from '../hooks/useAuth';

const UserProfile = () => {
  const { user, logout } = useAuth();

  if (!user) return null;

  return (
    <div className="flex items-center space-x-3">
      <img 
        src={user.picture} 
        alt={user.name}
        className="w-8 h-8 rounded-full border-2 border-green-500 shadow-sm"
      />
      <div className="hidden sm:block">
        <div className="text-sm font-semibold text-gray-800">{user.name}</div>
        <div className="text-xs text-gray-500">{user.email}</div>
      </div>
      <button
        onClick={logout}
        className="p-2 text-gray-600 hover:text-red-600 hover:bg-red-50 rounded-lg transition"
        title="로그아웃"
      >
        <LogOut size={16} />
      </button>
    </div>
  );
};

export default UserProfile;