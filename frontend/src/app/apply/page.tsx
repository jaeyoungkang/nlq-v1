"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

export default function PrototypeApplyPage() {
  const router = useRouter();
  const [values, setValues] = useState({
    name: "",
    email: "",
    purpose: "",
  });
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setValues((v) => ({ ...v, [name]: value }));
    if (message) setMessage(null);
  };

  const isValidEmail = (email: string) => /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/i.test(email.trim());
  
  const validate = () => {
    if (!values.name.trim()) return "이름을 입력해주세요.";
    if (!values.email.trim()) return "이메일을 입력해주세요.";
    if (!isValidEmail(values.email)) return "올바른 이메일 형식을 입력해주세요.";
    if (!values.purpose.trim() || values.purpose.trim().length < 10)
      return "신청 목적을 10자 이상으로 구체적으로 입력해주세요.";
    return null;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const err = validate();
    if (err) {
        setMessage({ type: "error", text: err });
        return;
    }

    try {
        setSubmitting(true);
        const res = await fetch("/api/prototype-apply", { 
            method: "POST", 
            headers: { "Content-Type": "application/json" }, 
            body: JSON.stringify(values) 
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "신청 실패");
        
        router.push(`/apply/success?email=${encodeURIComponent(values.email)}`);
    } catch (error) {
        const errorMessage = error instanceof Error ? error.message : "제출 중 오류가 발생했습니다.";
        setMessage({ type: "error", text: errorMessage });
    } finally {
        setSubmitting(false);
    }
};


  return (
    <div className="min-h-screen bg-slate-50">
      {/* Top Nav */}
      <nav className="border-b bg-white">
        <div className="max-w-4xl mx-auto px-6 h-16 flex items-center justify-between">
          <Link href="/" className="font-semibold text-slate-800 hover:text-primary-600 transition">
            ← 돌아가기
          </Link>
          <div className="text-slate-500 text-sm">서비스 체험 신청</div>
        </div>
      </nav>

      <main className="max-w-4xl mx-auto px-6 py-10">
        <div className="bg-white rounded-2xl shadow-lg border p-8">
          <h1 className="text-3xl font-bold text-slate-900 mb-2">프로토타입 체험 신청</h1>
          <p className="text-slate-600 mb-8">
            아래 정보를 작성해 주세요. 입력하신 메일주소로 안내 메일을 보내드립니다.
          </p>

          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">이름</label>
              <input
                name="name"
                value={values.name}
                onChange={handleChange}
                type="text"
                placeholder="홍길동"
                className="w-full rounded-lg border border-slate-300 p-3 bg-slate-50 focus:outline-none focus:ring-2 focus:ring-primary-500"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">
                이메일 (Gmail, Google Workspace(회사 도메인) 계정만 체험이 가능합니다. )
              </label>
              <input
                name="email"
                value={values.email}
                onChange={handleChange}
                type="email"
                placeholder="yourname@company.com"
                inputMode="email"
                className="w-full rounded-lg border border-slate-300 p-3 bg-slate-50 focus:outline-none focus:ring-2 focus:ring-primary-500"
                required
              />
              <p className="text-xs text-slate-500 mt-1">예: username@gmail.com</p>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">신청 목적</label>
              <textarea
                name="purpose"
                value={values.purpose}
                onChange={handleChange}
                rows={5}
                placeholder="팀/프로젝트 소개, 활용 예정 시나리오, 기대효과 등을 적어주세요. (10자 이상)"
                className="w-full rounded-lg border border-slate-300 p-3 bg-slate-50 focus:outline-none focus:ring-2 focus:ring-primary-500 resize-y"
                required
              />
            </div>

            {message && (
              <div
                className={`p-3 rounded-lg text-sm ${
                  message.type === "success"
                    ? "bg-green-50 border border-green-200 text-green-700"
                    : "bg-red-50 border border-red-200 text-red-700"
                }`}
              >
                {message.text}
              </div>
            )}

            <div className="flex gap-3">
              <button
                type="submit"
                disabled={submitting}
                className="inline-flex items-center justify-center rounded-lg bg-primary-600 hover:bg-primary-700 text-white font-semibold px-6 py-3 transition disabled:opacity-60 disabled:cursor-not-allowed"
              >
                {submitting ? "제출 중..." : "신청하기"}
              </button>
            </div>
          </form>
        </div>

        <p className="text-center text-xs text-slate-500 mt-6">
          제출 버튼을 누르면 개인정보 수집 및 이용에 동의한 것으로 간주됩니다. (체험 운영 목적 외 사용하지 않습니다)
        </p>
      </main>
    </div>
  );
}
