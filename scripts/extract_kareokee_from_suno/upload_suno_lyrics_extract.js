(async () => {
  console.log("🔍 جارٍ استخراج كامل النص مع الوسوم والتاقات وتوليد ملف SRT...");

  const match = window.location.pathname.match(/(?:edit|song|clip)\/([a-f0-9\-]+)/i);
  const songId = match ? match[1] : "4d990e52-cc82-4b9f-a9e8-a566d0797af4";

  let token = null;
  try { if (window.Clerk && window.Clerk.session) token = await window.Clerk.session.getToken(); } catch (e) {}
  if (!token) {
    const cookies = document.cookie.split(';');
    for (let c of cookies) {
      const [name, val] = c.trim().split('=');
      if (name === '__session' || name === 'jwt_token') { token = val; break; }
    }
  }

  if (!token) {
    console.error("❌ تعذر الحصول على توكن الجلسة.");
    return;
  }

  try {
    const res = await fetch(`https://studio-api.prod.suno.com/api/clip/${songId}`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });

    if (!res.ok) {
      console.error(`❌ فشل جلب البيانات: ${res.status}`);
      return;
    }

    const clipData = await res.json();
    const rawPrompt = clipData?.metadata?.prompt || "";
    const durationSec = clipData?.metadata?.duration || 307.5;

    if (!rawPrompt) {
      console.error("❌ لم يتم العثور على نص الكلمات.");
      return;
    }

    // الاحتفاظ بكافة الأسطر والوسوم كما هي بالضبط
    const allLines = rawPrompt.split('\n').map(l => l.trim()).filter(l => l.length > 0);

    const introPadding = 5;
    const outroPadding = 5;
    const availableTime = Math.max(20, durationSec - introPadding - outroPadding);
    const timePerLine = availableTime / allLines.length;

    function formatSRTTime(seconds) {
      if (seconds == null || isNaN(seconds)) return "00:00:00,000";
      const pad = (n, w = 2) => String(n).padStart(w, '0');
      const hrs = Math.floor(seconds / 3600);
      const mins = Math.floor((seconds % 3600) / 60);
      const secs = Math.floor(seconds % 60);
      const ms = Math.floor(Math.round((seconds % 1) * 1000));
      return `${pad(hrs)}:${pad(mins)}:${pad(secs)},${pad(ms, 3)}`;
    }

    let srtText = "";
    let fullTextWithTags = "";

    allLines.forEach((textLine, index) => {
      const startSec = introPadding + (index * timePerLine);
      const endSec = startSec + Math.min(timePerLine * 0.9, 5.0);

      srtText += `${index + 1}\n${formatSRTTime(startSec)} --> ${formatSRTTime(endSec)}\n${textLine}\n\n`;
      fullTextWithTags += `${textLine}\n`;
    });

    // 1. النسخ للحافظة
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(srtText);
      } else {
        copy(srtText);
      }
      console.log("📋 تم نسخ ملف SRT الكامل مع الوسوم إلى الحافظة!");
    } catch(e) {}

    // 2. التنزيل التلقائي كملف .srt
    try {
      const blob = new Blob([srtText], { type: 'text/plain;charset=utf-8' });
      const downloadUrl = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = downloadUrl;
      anchor.download = `suno_full_prompt_${songId.slice(0, 8)}.srt`;
      document.body.appendChild(anchor);
      anchor.click();
      document.body.removeChild(anchor);
      URL.revokeObjectURL(downloadUrl);
      console.log("💾 تم تنزيل ملف SRT مع الوسوم إلى مجلد Downloads!");
    } catch (e) {
      console.warn("تعذر التنزيل التلقائي للملف:", e);
    }

    console.log("%c✅ تم استخراج كافة الأسطر والوسوم وتوليد ملف SRT!", "color: #00ff00; font-size: 15px; font-weight: bold;");
    console.log("------------------ النص الكامل مع الوسوم ------------------");
    console.log(fullTextWithTags);
    console.log("------------------ محتوى ملف SRT الكامل ------------------");
    console.log(srtText);

    return srtText;

  } catch (err) {
    console.error("❌ حدث خطأ أثناء التنفيذ:", err);
  }
})();