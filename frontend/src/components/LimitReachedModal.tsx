'use client';

import React from 'react';
import { X } from 'lucide-react';
import GoogleLoginButton from './GoogleLoginButton';

interface LimitReachedModalProps {
  isOpen: boolean;
  onClose: () => void;
  remainingUsage: number;
  dailyLimit: number;
}

const LimitReachedModal: React.FC<LimitReachedModalProps> = ({
  isOpen,
  onClose,
  remainingUsage,
  dailyLimit
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-xl max-w-md w-full p-6 relative">
        {/* 닫기 버튼 */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-gray-400 hover:text-gray-600 transition"
          aria-label="닫기"
        >
          <X size={20} />
        </button>

        {/* 아이콘 */}
        <div className="text-center mb-4">
          <div className="text-6xl mb-4">🚫</div>
          <h2 className="text-xl font-bold text-gray-900 mb-2">
            일일 사용량이 모두 소진되었습니다
          </h2>
        </div>

        {/* 메시지 */}
        <div className="text-center mb-6">
          <p className="text-gray-600 mb-4 leading-relaxed">
            오늘 <span className="font-semibold text-primary-600">{dailyLimit}회</span> 무료 사용을 모두 완료했어요.
          </p>
          <p className="text-gray-600 mb-4 leading-relaxed">
            로그인하시면 <span className="font-semibold text-green-600">무제한</span>으로 이용하실 수 있습니다!
          </p>
        </div>

        {/* 로그인 버튼 */}
        <div className="space-y-3">
          <div className="flex justify-center">
            <GoogleLoginButton />
          </div>
          
          <button
            onClick={onClose}
            className="w-full py-3 text-gray-500 hover:text-gray-700 transition text-sm"
          >
            나중에 하기
          </button>
        </div>

        {/* 추가 정보 */}
        <div className="mt-4 pt-4 border-t border-gray-200">
          <p className="text-xs text-gray-500 text-center">
            내일 자정에 사용량이 초기화됩니다
          </p>
        </div>
      </div>
    </div>
  );
};

export default LimitReachedModal;