// File: frontend/components/WelcomeScreen.tsx
import React from 'react';
import { BarChart, Code, Database, BrainCircuit } from 'lucide-react';

interface WelcomeScreenProps {
  onSampleQuestionClick: (question: string) => void;
}

const WelcomeScreen = ({ onSampleQuestionClick }: WelcomeScreenProps) => {
  const features = [
    { icon: <Code />, title: "자연어 SQL 변환", description: "일상 언어로 질문하면 최적화된 BigQuery SQL을 생성" },
    { icon: <Database />, title: "실시간 데이터 조회", description: "테이블 메타데이터부터 복합 통계까지 즉시 조회" },
    { icon: <BrainCircuit />, title: "AI 기반 분석", description: "조회 결과에 대한 인사이트와 해석을 자동 제공" },
    { icon: <BarChart />, title: "인텔리전트 가이드", description: "상황에 맞는 다음 분석 단계와 질문을 추천" },
  ];
  
  const sampleQuestions = [
    "📊 상위 10개 레코드를 조회해주세요",
    "📝 테이블의 전체 행 수를 확인해주세요",
    "🏗️ 테이블 스키마 정보를 보여주세요",
    "⏰ 가장 최근 이벤트 시간을 알려주세요",
    "📈 시간대별 이벤트 분포를 분석해주세요",
    "🏆 상위 카테고리 순위를 보여주세요",
  ];

  return (
    <div className="welcome-message space-y-8" role="article" aria-label="환영 메시지">
        <div className="text-center">
            <p className="text-base text-gray-700 mb-6">
                BigQuery AI Assistant에 오신 것을 환영합니다. 📊 자연어를 통해 데이터베이스를 조회하고 분석할 수 있습니다.
            </p>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
                {features.map((feature, index) => (
                    <div key={index} className="bg-primary-50 border border-primary-100 rounded-lg p-4 text-center hover:shadow-md transition">
                        <div className="flex justify-center text-2xl mb-2 text-primary-600">{feature.icon}</div>
                        <h4 className="text-sm font-semibold text-primary-700 mb-2">{feature.title}</h4>
                        <p className="text-xs text-gray-600 leading-tight">{feature.description}</p>
                    </div>
                ))}
            </div>
        </div>

        <div>
            <h3 className="text-base font-semibold text-gray-700 mb-4">🗃️ 데이터소스 정보</h3>
            <div className="bg-gray-50 border border-gray-200 rounded-lg p-5">
                <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-3 gap-2">
                    <h4 className="text-base font-semibold text-gray-700">Events 데이터테이블</h4>
                    <span className="bg-primary-500 text-white text-xs px-2 py-1 rounded">2021-01-31 스냅샷</span>
                </div>
                <p className="text-sm text-gray-600 mb-4 leading-relaxed">
                    사용자 이벤트 로그 데이터를 포함하고 있으며, 웹 애플리케이션에서 발생한 다양한 사용자 행동을 추적합니다.
                </p>
                <div className="space-y-2">
                    <div className="flex justify-between py-2 border-b border-gray-200">
                        <span className="font-medium text-gray-700 text-sm">테이블 ID</span>
                        <span className="text-gray-600 text-sm font-mono break-all">nlq-ex.test_dataset.events_20210131</span>
                    </div>
                    <div className="flex justify-between py-2">
                        <span className="font-medium text-gray-700 text-sm">주요 필드</span>
                        <div className="flex flex-wrap gap-2 justify-end">
                            <span className="bg-white border border-gray-300 text-gray-700 text-xs px-2 py-1 rounded font-mono">user_id</span>
                            <span className="bg-white border border-gray-300 text-gray-700 text-xs px-2 py-1 rounded font-mono">event_timestamp</span>
                            <span className="bg-white border border-gray-300 text-gray-700 text-xs px-2 py-1 rounded font-mono">category</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <div className="sample-questions">
            <p className="text-sm font-semibold text-gray-700 mb-3">💡 빠른 시작 질문:</p>
            <div className="flex flex-wrap gap-2">
                {sampleQuestions.map((q, index) => (
                    <button
                        key={index}
                        onClick={() => onSampleQuestionClick(q.replace(/📊 |📝 |🏗️ |⏰ |📈 |🏆 /g, ''))}
                        className="bg-gray-100 border border-gray-300 text-gray-700 text-sm px-3 py-2 rounded-lg hover:bg-primary-50 hover:border-primary-500 hover:text-primary-700 transition"
                    >
                        {q}
                    </button>
                ))}
            </div>
        </div>
    </div>
  );
};

export default WelcomeScreen;