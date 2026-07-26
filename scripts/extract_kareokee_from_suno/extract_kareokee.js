(async () => {
  console.log("🔍 جارٍ جلب توكن الجلسة واستخراج ملف SRT من Suno API...");

  // 1. استخراج ID الأغنية من رابط الصفحة
  const match = window.location.pathname.match(/(?:edit|song)\/([a-f0-9\-]+)/i);
  const songId = match ? match[1] : null;

  if (!songId) {
    console.error("❌ لم يتم العثور على Song ID في رابط الصفحة.");
    return;
  }

  // 2. البحث عن التوكن تلقائياً من جلسة Clerk أو Cookies
  let token = null;
  try {
    if (window.Clerk && window.Clerk.session) {
      token = await window.Clerk.session.getToken();
    }
  } catch (e) {}

  if (!token) {
    const cookies = document.cookie.split(';');
    for (let c of cookies) {
      const [name, val] = c.trim().split('=');
      if (name === '__session' || name === 'jwt_token') {
        token = val;
        break;
      }
    }
  }

  if (!token) {
    console.error("❌ تعذر الوصول لتوكن الجلسة. تأكد من إتمام تسجيل الدخول في سونو.");
    return;
  }

  console.log("🔑 تم العثور على التوكن، جارٍ جلب التوقيتات الدقيقة للكلمات...");

  // 3. طلب الكلمات المتزامنة من API سونو الرسمية
  const apiUrl = `https://studio-api.prod.suno.com/api/gen/${songId}/aligned_lyrics/v2/`;
  
  try {
    const res = await fetch(apiUrl, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      }
    });

    if (!res.ok) {
      console.error(`❌ فشل الطلب: ${res.status} ${res.statusText}`);
      return;
    }

    const data = await res.json();
    const alignedWords = data.aligned_words || data.words || data;

    if (!alignedWords || !Array.isArray(alignedWords) || alignedWords.length === 0) {
      console.error("❌ لم يتم العثور على كلمات متزامنة لهذا المقطع حتى الآن.");
      return;
    }

    // 4. تحويل الوقت إلى صيغة SRT
    function formatSRTTime(seconds) {
      if (seconds == null || isNaN(seconds)) return "00:00:00,000";
      const pad = (n, width = 2) => String(n).padStart(width, '0');
      const hrs = Math.floor(seconds / 3600);
      const mins = Math.floor((seconds % 3600) / 60);
      const secs = Math.floor(seconds % 60);
      const ms = Math.floor(Math.round((seconds % 1) * 1000));
      return `${pad(hrs)}:${pad(mins)}:${pad(secs)},${pad(ms, 3)}`;
    }

    // 5. بناء نص الـ SRT
    let srtText = "";
    let blockIndex = 1;
    let currentBlock = [];
    let blockStart = null;
    let blockEnd = null;

    alignedWords.forEach((item, idx) => {
      const wordText = (item.word || item.text || "").trim();
      const start = item.start_s ?? item.start;
      const end = item.end_s ?? item.end;

      if (start === undefined || end === undefined || !wordText) return;

      if (blockStart === null) blockStart = start;
      blockEnd = end;
      currentBlock.push(wordText);

      const nextItem = alignedWords[idx + 1];
      const nextStart = nextItem ? (nextItem.start_s ?? nextItem.start) : null;
      const pause = nextStart != null ? (nextStart - end) : 0;

      // إنهاء السطر عند: توقف زمني > 1.0 ثانية أو تجميع 6 كلمات أو وجود سطر جديد
      if (pause > 1.0 || currentBlock.length >= 6 || wordText.includes('\n') || idx === alignedWords.length - 1) {
        const lineText = currentBlock.join(' ').replace(/\n+/g, ' ').trim();
        if (lineText) {
          srtText += `${blockIndex}\n${formatSRTTime(blockStart)} --> ${formatSRTTime(blockEnd)}\n${lineText}\n\n`;
          blockIndex++;
        }
        currentBlock = [];
        blockStart = null;
      }
    });

    if (srtText) {
      // محاولة النسخ عبر Clipboard API
      if (navigator.clipboard && navigator.clipboard.writeText) {
        try {
          await navigator.clipboard.writeText(srtText);
          console.log("📋 تم نسخ النص إلى الحافظة بنجاح!");
        } catch (e) {}
      }

      // تنزيل ملف .srt تلقائياً إلى الجهاز
      try {
        const blob = new Blob([srtText], { type: 'text/plain;charset=utf-8' });
        const downloadUrl = URL.createObjectURL(blob);
        const downloadAnchor = document.createElement('a');
        downloadAnchor.href = downloadUrl;
        downloadAnchor.download = `suno_lyrics_${songId.slice(0, 8)}.srt`;
        document.body.appendChild(downloadAnchor);
        downloadAnchor.click();
        document.body.removeChild(downloadAnchor);
        URL.revokeObjectURL(downloadUrl);
        console.log("💾 تم تنزيل ملف SRT تلقائياً إلى مجلد التنزيلات (Downloads)!");
      } catch (e) {
        console.warn("تعذر تنزيل الملف تلقائياً:", e);
      }

      console.log("✅ تم استخراج التوقيتات بنجاح!");
      console.log("------------------ نص ملف SRT ------------------");
      console.log(srtText);
      console.log("------------------------------------------------");

      return srtText;
    }

  } catch (err) {
    console.error("❌ حدث خطأ أثناء تنفيذ الطلب:", err);
  }
})();