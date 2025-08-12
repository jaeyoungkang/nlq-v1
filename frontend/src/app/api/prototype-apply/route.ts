import { NextResponse } from "next/server";
import { Resend } from "resend";

const resend = new Resend(process.env.RESEND_API_KEY);

export async function POST(req: Request) {
  try {
    const { name, email, purpose } = await req.json();

    if (!name?.trim() || !email?.trim() || !purpose?.trim()) {
      return NextResponse.json({ error: "모든 필드를 입력해주세요." }, { status: 400 });
    }
    
    const isValidEmail = (email: string) => /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/i.test(email.trim());
    if (!isValidEmail) {
      return NextResponse.json({ error: "이메일 포멧이 아닙니다." }, { status: 400 });
    }

    const safe = (s: string) =>
      s.replace(/[&<>"']/g, (m) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[m]!));

    const adminHtml = `
      <h2>프로토타입 체험 신청</h2>
      <p><b>이름:</b> ${safe(name)}</p>
      <p><b>이메일:</b> ${safe(email)}</p>
      <p><b>신청 목적:</b><br/>${safe(purpose).replace(/\n/g, "<br/>")}</p>
      <hr/>
      <p style="font-size:12px;color:#64748b">본 메일은 시스템에 의해 자동 발송되었습니다.</p>
    `;

    const applicantHtml = `
      <p>${safe(name)}님, 프로토타입 체험 신청이 <b>정상 접수</b>되었습니다. 빠르게 검토 후 연락드릴게요.</p>
      <p style="margin-top:16px"><b>제출 내역</b></p>
      <ul>
        <li><b>이메일:</b> ${safe(email)}</li>
      </ul>
      <p><b>신청 목적</b><br/>${safe(purpose).replace(/\n/g, "<br/>")}</p>
      <hr/>
      <p style="font-size:12px;color:#64748b">이 메일은 회신 가능하며, 문의는 이 메일에 답장해 주세요.</p>
    `;

    // 1) 관리자 메일 (필수)
    const adminSend = resend.emails.send({
      from: `Prototype Apply <${process.env.FROM_EMAIL || "no-reply@onresend.com"}>`,
      to: [process.env.APPLY_RECEIVE_EMAIL!],
      subject: "새로운 프로토타입 체험 신청",
      html: adminHtml,
      replyTo: email, // 답장 시 신청자에게 회신되도록
    });

    // 2) 신청자 확인 메일 (베스트에포트: 실패해도 성공화면은 보여줌)
    const applicantSend = resend.emails.send({
      from: `Prototype Apply <${process.env.FROM_EMAIL || "no-reply@onresend.com"}>`,
      to: [email],
      subject: "프로토타입 체험 신청이 접수되었습니다",
      html: applicantHtml,
    });

    // 둘 다 시도하되, 관리자 메일 실패 시에는 실패 반환 / 신청자 메일은 실패 무시
    const [adminResult, applicantResult] = await Promise.allSettled([adminSend, applicantSend]);

    if (adminResult.status === "rejected") {
      console.error("Admin mail failed:", adminResult.reason);
      return NextResponse.json({ error: "메일 전송 실패" }, { status: 500 });
    }
    if (applicantResult.status === "rejected") {
      console.warn("Applicant ack mail failed:", applicantResult.reason);
      // 굳이 실패 반환하지 않음: 성공 화면은 계속 표시
    }

    return NextResponse.json({ ok: true });
  } catch (e) {
    console.error(e);
    return NextResponse.json({ error: "서버 오류" }, { status: 500 });
  }
}
