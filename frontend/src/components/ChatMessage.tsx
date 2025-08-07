// File: frontend/components/ChatMessage.tsx
import React from 'react';
import ReactMarkdown from 'react-markdown';
import { User, Bot } from 'lucide-react';
import { Message } from '../stores/useChatStore';

interface ChatMessageProps {
  msg: Message;
  showLabel?: boolean; // 라벨 표시 여부 (연속 메시지 처리용)
}

const ChatMessage = ({ msg, showLabel = true }: ChatMessageProps) => {
  const isUser = msg.type === 'user';

  const renderAssistantContent = () => {
    if (msg.content === 'Thinking...') {
      return (
        <div className="flex items-center space-x-2 text-gray-600">
            <span>처리 중</span>
            <div className="flex space-x-1">
                <div className="w-1 h-1 bg-primary-500 rounded-full loading-dot"></div>
                <div className="w-1 h-1 bg-primary-500 rounded-full loading-dot"></div>
                <div className="w-1 h-1 bg-primary-500 rounded-full loading-dot"></div>
            </div>
        </div>
      );
    }
    
    const hasSql = msg.sql;

    // 메인 콘텐츠 렌더링 (모든 응답 타입에 대해 공통적으로 처리)
    const renderMainContent = () => {
      if (!msg.content) {
        return <div className="text-gray-500 italic">응답 내용이 없습니다.</div>;
      }
      
      return (
        <div className="prose prose-sm max-w-none">
          <ReactMarkdown>{msg.content}</ReactMarkdown>
        </div>
      );
    };

    // SQL 쿼리 렌더링
    const renderSqlSection = () => {
      if (!hasSql) return null;
      
      return (
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
          <h4 className="text-xs text-gray-500 mb-2 font-semibold uppercase tracking-wide">생성된 SQL</h4>
          <pre className="text-sm font-mono text-gray-800 whitespace-pre-wrap overflow-x-auto">
            <code>{msg.sql}</code>
          </pre>
        </div>
      );
    };

    // 데이터 테이블 렌더링
    const renderDataTable = () => {
      // 1. msg.data가 undefined이거나 null이면 아무것도 렌더링하지 않음
      if (!msg.data) {
        return null;
      }

      // 2. msg.data가 빈 배열이면 "결과 없음" 메시지를 표시
      if (msg.data.length === 0) {
        return (
          <div className="bg-yellow-50 border border-yellow-200 text-yellow-700 p-4 rounded-lg">
            조회 결과가 없습니다.
          </div>
        );
      }
      
      // 3. 데이터가 존재하면 테이블을 렌더링
      // 이 시점에서는 msg.data가 비어있지 않은 배열임이 보장됨
      return (
        <div className="border border-gray-200 rounded-lg overflow-hidden">
          <div className="bg-gray-50 px-4 py-3 border-b border-gray-200 flex justify-between items-center">
            <span className="font-semibold text-gray-700">조회 결과</span>
            <div className="text-sm text-gray-500">{msg.data.length.toLocaleString()}행</div>
          </div>
          <div className="overflow-x-auto max-h-72">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 sticky top-0">
                <tr>
                  {Object.keys(msg.data[0]).map(key => (
                    <th key={key} className="px-3 py-2 text-left font-semibold text-sm text-gray-700 bg-gray-50 border-b border-gray-200">
                      {key}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {msg.data.map((row: Record<string, unknown>, rowIndex: number) => (
                  <tr key={rowIndex} className="hover:bg-gray-50">
                    {Object.values(row).map((value: unknown, cellIndex: number) => (
                      <td 
                        key={cellIndex} 
                        className="px-3 py-2 text-sm border-b border-gray-100 max-w-xs truncate" 
                        title={String(value)}
                      >
                        {String(value)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      );
    };

    // 전체 콘텐츠 구성
    return (
      <div className="space-y-4">
        {/* 메인 콘텐츠 (가이드, 분석, 일반 응답 등 모든 타입) */}
        {renderMainContent()}
        
        {/* SQL 쿼리 섹션 (있는 경우만) */}
        {renderSqlSection()}
        
        {/* 데이터 테이블 섹션 (있는 경우만) */}
        {renderDataTable()}
      </div>
    );
  };

  return (
    <div className="message mb-8">
      {/* 라벨 표시 조건: showLabel이 true일 때만 표시 */}
      {showLabel && (
        <div className={`text-sm font-semibold mb-2 ${isUser ? 'text-primary-600' : 'text-gray-700'}`}>
          {isUser ? 'User' : 'Assistant'}
        </div>
      )}
      <div className={`text-sm leading-relaxed ${isUser ? 'bg-primary-50 border-l-4 border-primary-500 p-4 rounded-r-lg' : ''}`}>
        {isUser ? (
          <div className="prose prose-sm max-w-none">
            <ReactMarkdown>{msg.content}</ReactMarkdown>
          </div>
        ) : (
          renderAssistantContent()
        )}
      </div>
    </div>
  );
};

export default ChatMessage;