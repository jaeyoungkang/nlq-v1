"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";

export default function ApplySuccessPage() {
  const searchParams = useSearchParams();
  const email = searchParams.get("email");

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-slate-50 px-6">
      <div className="bg-white rounded-2xl shadow-lg border p-8 max-w-md text-center">
        <h1 className="text-3xl font-bold text-green-600 mb-4">✅ 신청 완료</h1>
        <p className="text-slate-700 mb-4">
          신청이 성공적으로 접수되었습니다.
        </p>

        {email && (
          <p className="text-primary-600 font-medium mb-6">
            확인 메일을 보냈습니다: <span className="font-bold">{email}</span>
          </p>
        )}

        <p className="text-slate-500 mb-8">
          입력하신 Gmail 주소로 안내 메일을 발송했습니다.<br />
          빠르게 검토 후 연락드리겠습니다.
        </p>

        <Link
          href="/"
          className="inline-block bg-primary-600 hover:bg-primary-700 text-white px-6 py-3 rounded-lg font-semibold transition"
        >
          홈으로 돌아가기
        </Link>
      </div>
    </div>
  );
}
