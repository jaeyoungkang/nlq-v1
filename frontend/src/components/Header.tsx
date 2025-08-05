// File: frontend/components/Header.tsx
// 역할: 페이지 상단 헤더 UI

import React from 'react';

const Header = () => {
  return (
    <header className="px-6 py-6 text-center border-b border-gray-200 bg-white flex-shrink-0">
        <h1 className="text-3xl font-bold gemini-gradient-text mb-1">BigQuery AI Assistant</h1>
        <p className="text-sm text-gray-600">자연어로 BigQuery 데이터를 조회하세요</p>
    </header>
  );
};

export default Header;