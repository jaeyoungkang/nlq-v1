"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";

// --- 타입 ---
interface DemoMessage {
  type: "user" | "assistant";
  content: string | React.ReactNode;
  delay?: number; // 이 메시지까지 대기 시간 (ms). 없으면 기본 간격 적용
}

// --- UI 컴포넌트 ---
const SQLDemo = ({ sql, resultText }: { sql: string; resultText: string }) => (
  <>
    <div className="bg-slate-100 p-3 rounded-lg mb-3">
      <div className="text-xs text-slate-500 mb-1 uppercase tracking-wide font-semibold">생성된 SQL</div>
      <pre className="text-sm font-mono whitespace-pre-wrap text-slate-800">{sql}</pre>
    </div>
    <div className="bg-blue-50 border border-blue-200 p-3 rounded-lg">
      <div className="text-sm font-semibold text-blue-700">📊 조회 결과</div>
      <div className="text-sm text-blue-900">{resultText}</div>
    </div>
  </>
);

const AnalysisDemo = ({ analysisText }: { analysisText: string }) => (
  <div className="bg-primary-50 border border-primary-200 p-3 rounded-lg">
    <div className="text-sm font-semibold text-primary-700 mb-1">AI 분석 결과</div>
    <div className="text-sm text-primary-900">{analysisText}</div>
  </div>
);

// --- 페이지 ---
export default function LandingPage() {
  const [currentScenario, setCurrentScenario] = useState<"basic" | "analysis" | "complex">("basic");

  // 1) 시나리오 정의는 메모이즈 (렌더마다 새 객체/JSX 방지)
  const scenarios = useMemo<Record<"basic" | "analysis" | "complex", { messages: DemoMessage[] }>>(
    () => ({
      basic: {
        messages: [
          { type: "user", content: "상위 10개 레코드를 조회해주세요", delay: 0 },
          {
            type: "assistant",
            content: (
              <SQLDemo
                sql='SELECT * FROM `nlq-ex.test_dataset.events_20210131` LIMIT 10;'
                resultText="10행 조회 완료"
              />
            ),
            delay: 1500,
          },
        ],
      },
      analysis: {
        messages: [
          { type: "user", content: "시간대별 이벤트 분포를 분석해주세요", delay: 0 },
          {
            type: "assistant",
            content: (
              <SQLDemo
                sql="SELECT EXTRACT(HOUR FROM event_timestamp) as hour, COUNT(*) as event_count FROM `nlq-ex.test_dataset.events_20210131` GROUP BY hour ORDER BY hour;"
                resultText="24시간 분포 데이터"
              />
            ),
            delay: 2000,
          },
          {
            type: "assistant",
            content: (
              <AnalysisDemo analysisText="🤖 분석 결과: 오후 2-4시에 가장 많은 활동이 발생하며, 새벽 시간대는 활동이 현저히 줄어듭니다." />
            ),
            delay: 1500,
          },
        ],
      },
      complex: {
        messages: [
          { type: "user", content: "카테고리별 이벤트 수와 고유 사용자 수를 함께 보여주세요", delay: 0 },
          {
            type: "assistant",
            content: (
              <SQLDemo
                sql="SELECT category, COUNT(*) as total_events, COUNT(DISTINCT user_id) as unique_users FROM `nlq-ex.test_dataset.events_20210131` GROUP BY category ORDER BY total_events DESC;"
                resultText="카테고리별 복합 통계"
              />
            ),
            delay: 2500,
          },
        ],
      },
    }),
    []
  );

  const DEFAULT_STEP = 800; // delay가 명시되지 않으면 사용하는 기본 간격
  const allMessages = scenarios[currentScenario].messages;

  // 2) 애니메이션은 인덱스만 상태로 관리
  const [stepIndex, setStepIndex] = useState(0);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // 시나리오가 바뀌면 인덱스 리셋 + 기존 타이머 정리
  useEffect(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    setStepIndex(0);
  }, [currentScenario]);

  // 단일 타이머로 다음 단계 예약 (stepIndex 기반)
  useEffect(() => {
    // 종료 조건: 모든 메시지를 표시했으면 타이머 중단
    if (stepIndex >= allMessages.length) return;

    // 다음 트리거까지 대기 시간 계산
    const delay =
      allMessages[stepIndex]?.delay ?? (stepIndex === 0 ? 0 : DEFAULT_STEP);

    timerRef.current = setTimeout(() => {
      setStepIndex((i) => i + 1);
    }, delay);

    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
    };
    // 의존성에 allMessages 넣으면 안전 (scenarios는 useMemo로 고정)
  }, [stepIndex, allMessages]);

  // 렌더링에 사용할 메시지 (파생 값) — 상태 아님
  const messagesToRender = allMessages.slice(0, stepIndex);

  // 스크롤 자동 하단
  const listRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [stepIndex]);

  return (
    <div className="font-sans text-slate-800 overflow-x-hidden bg-white">
      {/* Navigation */}
      <nav className="fixed top-0 left-0 right-0 z-50 border-b border-slate-200 bg-white/80 backdrop-blur-md">
        <div className="max-w-6xl mx-auto px-6 flex justify-between items-center h-16">
          <div className="flex items-center space-x-2 font-bold text-lg text-primary-600">
            <span className="text-2xl">🤖</span>
            <span>Data Analysis AI Assistant</span>
          </div>
          <div className="hidden md:flex items-center space-x-8">
            <a href="#features" className="text-slate-600 hover:text-primary-600 transition">기능</a>
            <a href="#use-cases" className="text-slate-600 hover:text-primary-600 transition">활용사례</a>
            <a href="#demo" className="text-slate-600 hover:text-primary-600 transition">데모</a>
            <Link href="/apply" className="bg-primary-500 text-white px-4 py-2 rounded-lg hover:bg-primary-600 transition font-semibold">
              프로토타입 체험
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="relative min-h-screen flex items-center bg-gradient-to-br from-amber-50 via-orange-50 to-amber-100 pt-16">
        <div className="max-w-6xl mx-auto px-6 w-full">
          <div className="grid md:grid-cols-2 gap-16 items-center">
            <div className="space-y-8">
              <h1 className="text-5xl md:text-6xl font-bold leading-tight text-slate-900">
                SQL 없이도 <span className="gradient-text">일상언어</span>로<br />데이터를 조회하세요
              </h1>
              <p className="text-xl text-slate-600 leading-relaxed">
                복잡한 BigQuery 쿼리를 일상 언어로 변환하고, AI가 자동으로 데이터를 분석해드립니다.
              </p>
              <div className="flex space-x-8 pt-4">
                <div className="text-center">
                  <div className="text-3xl font-bold text-primary-600">5초</div>
                  <div className="text-sm text-slate-500">평균 응답 시간</div>
                </div>
                <div className="text-center">
                  <div className="text-3xl font-bold text-primary-600">98%</div>
                  <div className="text-sm text-slate-500">SQL 변환 정확도</div>
                </div>
                <div className="text-center">
                  <div className="text-3xl font-bold text-primary-600">0</div>
                  <div className="text-sm text-slate-500">SQL 지식 필요</div>
                </div>
              </div>
              <div className="flex flex-col sm:flex-row gap-4 pt-4">
                <Link href="/apply" className="bg-primary-500 text-white px-8 py-4 rounded-xl font-semibold hover:bg-primary-600 transition transform hover:-translate-y-1 shadow-lg hover:shadow-xl">
                  🚀 프로토타입 체험하기
                </Link>
                <a href="#demo" className="bg-white border-2 border-primary-500 text-primary-500 px-8 py-4 rounded-xl font-semibold hover:bg-primary-500 hover:text-white transition">
                  ▶️ 데모 보기
                </a>
              </div>
            </div>
            <div className="relative">
              <div className="bg-white rounded-2xl shadow-2xl overflow-hidden transform animate-float" style={{ perspective: "1000px" }}>
                <div className="p-6 space-y-4">
                  <div className="flex justify-end">
                    <div className="bg-primary-500 text-white px-4 py-3 rounded-2xl rounded-br-sm max-w-xs">
                      &quot;월별 매출 상위 10개 제품은?&quot;
                    </div>
                  </div>
                  <div className="space-y-3">
                    <SQLDemo
                      sql="SELECT product_name, SUM(revenue) FROM sales GROUP BY product_name ORDER BY SUM(revenue) DESC LIMIT 10;"
                      resultText="상위 10개 제품 리스트 표시"
                    />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="py-24 bg-slate-50">
        <div className="max-w-6xl mx-auto px-6">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-bold mb-4 text-slate-900">🚀 핵심 기능</h2>
            <p className="text-xl text-slate-600">복잡한 데이터 분석을 간단하게 만드는 핵심 기능들</p>
          </div>
          <div className="grid md:grid-cols-3 gap-8">
            <div className="bg-white p-8 rounded-2xl shadow-lg hover:shadow-xl transition-shadow group border">
              <div className="text-4xl mb-6">💬</div>
              <h3 className="text-2xl font-bold mb-4 text-slate-900 group-hover:text-primary-600 transition">자연어 SQL 변환</h3>
              <p className="text-slate-600 mb-6">&quot;상위 10개 매출 제품은?&quot; 같은 일상 언어를 자동으로 BigQuery SQL로 변환합니다.</p>
            </div>
            <div className="bg-white p-8 rounded-2xl shadow-lg hover:shadow-xl transition-shadow group border">
              <div className="text-4xl mb-6">🤖</div>
              <h3 className="text-2xl font-bold mb-4 text-slate-900 group-hover:text-primary-600 transition">AI 기반 분석</h3>
              <p className="text-slate-600 mb-6">조회한 데이터를 AI가 자동으로 분석하여 인사이트와 비즈니스 해석을 제공합니다.</p>
            </div>
            <div className="bg-white p-8 rounded-2xl shadow-lg hover:shadow-xl transition-shadow group border">
              <div className="text-4xl mb-6">💡</div>
              <h3 className="text-2xl font-bold mb-4 text-slate-900 group-hover:text-primary-600 transition">인텔리전트 가이드</h3>
              <p className="text-slate-600 mb-6">상황에 맞는 질문 제안과 분석 방향을 추천하여 효율적인 데이터 탐색을 지원합니다.</p>
            </div>
          </div>
        </div>
      </section>

      {/* Demo */}
      <section id="demo" className="py-24 bg-slate-50">
        <div className="max-w-4xl mx-auto px-6">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-bold mb-4 text-slate-900">🎮 라이브 데모</h2>
            <p className="text-xl text-slate-600">실제로 어떻게 작동하는지 직접 체험해보세요</p>
          </div>
          <div className="text-center mb-8">
            <h3 className="text-lg font-semibold mb-4 text-slate-800">💬 시나리오 선택</h3>
            <div className="flex flex-wrap justify-center gap-3">
              {(["basic", "analysis", "complex"] as const).map((scenario) => (
                <button
                  key={scenario}
                  onClick={() => setCurrentScenario(scenario)}
                  className={`px-6 py-3 rounded-lg font-semibold transition ${
                    currentScenario === scenario ? "bg-primary-600 text-white" : "bg-white text-slate-700 hover:bg-primary-100"
                  }`}
                >
                  {scenario === "basic" && "📊 기본 조회"}
                  {scenario === "analysis" && "🤖 AI 분석"}
                  {scenario === "complex" && "🔍 복합 쿼리"}
                </button>
              ))}
            </div>
          </div>

          <div className="bg-white border border-slate-200 rounded-2xl shadow-xl overflow-hidden mb-8">
            <div ref={listRef} className="h-96 p-6 bg-slate-50 overflow-y-auto space-y-4">
              {messagesToRender.map((message, index) => (
                <div key={index} className="animate-fade-in-up">
                  {message.type === "user" ? (
                    <div className="flex justify-end">
                      <div className="bg-primary-500 text-white px-4 py-3 rounded-2xl rounded-br-sm max-w-xs">
                        {message.content}
                      </div>
                    </div>
                  ) : (
                    <div className="flex justify-start">
                      <div className="bg-white border border-slate-200 px-4 py-3 rounded-2xl rounded-bl-sm max-w-md">
                        {message.content}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>

            <div className="p-6 bg-white border-t border-slate-200 flex flex-col sm:flex-row gap-4">
              <input type="text" placeholder="직접 질문해보세요..." className="flex-1 p-3 border border-slate-300 rounded-lg bg-slate-50" readOnly />
              <Link href="/apply" className="bg-primary-500 text-white px-6 py-3 rounded-lg font-semibold hover:bg-primary-600 transition text-center">
                실제 체험하기
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Final CTA & Footer */}
      <section className="py-20 bg-gradient-to-r from-slate-900 to-gray-800 text-white">
        <div className="max-w-4xl mx-auto px-6 text-center">
          <h2 className="text-4xl font-bold mb-6">🚀 지금 체험 해보세요</h2>
          <p className="text-xl text-slate-300 mb-8 leading-relaxed">
            복잡한 SQL 없이도 데이터를 자유자재로 활용할 수 있습니다.<br />
            몇 분 안에 첫 번째 인사이트를 발견해보세요.
          </p>
          <Link href="/apply" className="inline-block bg-primary-600 text-white px-12 py-4 rounded-xl text-lg font-semibold hover:bg-primary-700 transition transform hover:-translate-y-1 shadow-2xl">
            💫 무료로 체험하기
          </Link>
        </div>
      </section>

      <footer className="bg-slate-900 text-white py-12">
        <div className="max-w-6xl mx-auto px-6 text-center">
          <p className="text-slate-400">&copy; 2025 Data Analysis AI Assistant.</p>
        </div>
      </footer>

      <style jsx global>{`
        @keyframes float { 0%,100% { transform: translateY(0px); } 50% { transform: translateY(-20px); } }
        .animate-float { animation: float 6s ease-in-out infinite; }
        .gradient-text { background: linear-gradient(135deg, #d97706, #f59e0b); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }
        html { scroll-behavior: smooth; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
        .animate-fade-in-up { animation: fadeIn 0.5s ease forwards; }
      `}</style>
    </div>
  );
}
