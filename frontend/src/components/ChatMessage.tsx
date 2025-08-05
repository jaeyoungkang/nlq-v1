// File: frontend/components/ChatMessage.tsx
import React from 'react';
import ReactMarkdown from 'react-markdown';
import { User, Bot } from 'lucide-react';
import { Message } from '../stores/useChatStore';

const ChatMessage = ({ msg }: { msg: Message }) => {
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

    if (!msg.data && !hasSql) {
      // FIX 1: ReactMarkdown을 div로 감싸고 className 적용
      return <div className="prose prose-sm max-w-none"><ReactMarkdown>{msg.content}</ReactMarkdown></div>;
    }

    return (
      <div className="space-y-4">
        {/* FIX 1: ReactMarkdown을 div로 감싸고 className 적용 */}
        <div className="prose prose-sm max-w-none"><ReactMarkdown>{msg.content}</ReactMarkdown></div>
        {hasSql && (
          <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
            <h4 className="text-xs text-gray-500 mb-2 font-semibold uppercase tracking-wide">생성된 SQL</h4>
            <pre className="text-sm font-mono text-gray-800 whitespace-pre-wrap overflow-x-auto">
              <code>{msg.sql}</code>
            </pre>
          </div>
        )}
        {/* FIX 2: 'msg.data'가 undefined일 가능성을 명시적으로 확인 */}
        {msg.data && msg.data.length > 0 && (
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
                      <th key={key} className="px-3 py-2 text-left font-semibold text-sm text-gray-700 bg-gray-50 border-b border-gray-200">{key}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {/* FIX 3: `any` 대신 구체적인 타입 사용 */}
                  {msg.data.map((row: Record<string, unknown>, rowIndex: number) => (
                    <tr key={rowIndex} className="hover:bg-gray-50">
                      {Object.values(row).map((value: unknown, cellIndex: number) => (
                        <td key={cellIndex} className="px-3 py-2 text-sm border-b border-gray-100 max-w-xs truncate" title={String(value)}>{String(value)}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
        {/* FIX 2: 'msg.data'가 undefined일 가능성을 명시적으로 확인 */}
        {msg.data && msg.data.length === 0 && (
          <div className="bg-yellow-50 border border-yellow-200 text-yellow-700 p-4 rounded-lg">
            조회 결과가 없습니다.
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="message mb-8">
      <div className={`text-sm font-semibold mb-2 ${isUser ? 'text-primary-600' : 'text-gray-700'}`}>
        {isUser ? 'User' : 'Assistant'}
      </div>
      <div className={`text-sm leading-relaxed ${isUser ? 'bg-primary-50 border-l-4 border-primary-500 p-4 rounded-r-lg' : ''}`}>
        {/* FIX 1: ReactMarkdown을 div로 감싸고 className 적용 */}
        {isUser ? <div className="prose prose-sm max-w-none"><ReactMarkdown>{msg.content}</ReactMarkdown></div> : renderAssistantContent()}
      </div>
    </div>
  );
};

export default ChatMessage;