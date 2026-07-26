import sys
import re
import json
import os


def normalize_text(text):
    """إزالة التشكيل والأقواس والرموز للحصول على الأحرف الصافية فقط لغرض التتبع"""
    text = re.sub(r"\[.*?\]", "", text)  # إزالة [Verse] و [Instrumental]
    text = re.sub(r"\(.*?\)", "", text)  # إزالة الملاحظات
    text = re.sub(r"[\u064B-\u0652\u0670]", "", text)  # إزالة التشكيل والحركات
    text = re.sub(r"[^\w\s]", "", text)  # إزالة علامات الترقيم
    return text.strip()


def parse_raw_input(filepath):
    """قراءة المدخلات الخام سواء كانت ملف SRT/TXT أو JSON مباشر من API سونو"""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read().strip()

    events = []

    # 1. محاولة قراءة الملف كـ JSON مباشر من API سونو
    try:
        data = json.loads(content)
        aligned_words = (
            data.get("aligned_words")
            or data.get("words")
            or (data if isinstance(data, list) else None)
        )
        if aligned_words and isinstance(aligned_words, list):
            for item in aligned_words:
                word_text = (item.get("word") or item.get("text") or "").strip()
                start = (
                    item.get("start_s")
                    if item.get("start_s") is not None
                    else item.get("start")
                )
                end = (
                    item.get("end_s")
                    if item.get("end_s") is not None
                    else item.get("end")
                )
                if start is not None and end is not None and word_text:
                    events.append(
                        {
                            "start_s": float(start),
                            "end_s": float(end),
                            "text": word_text,
                        }
                    )
            if events:
                return events, "JSON (API Direct)"
    except Exception:
        pass

    # 2. قراءة الملف كـ SRT / TXT خام
    pattern = re.compile(
        r"(\d+)\n(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\n([\s\S]*?)(?=\n\n|\Z)"
    )
    matches = pattern.findall(content)

    def srt_to_seconds(srt_time_str):
        hrs, mins, secs_ms = srt_time_str.split(":")
        secs, ms = secs_ms.split(",")
        return int(hrs) * 3600 + int(mins) * 60 + int(secs) + int(ms) / 1000.0

    for match in matches:
        start_s = srt_to_seconds(match[1])
        end_s = srt_to_seconds(match[2])
        text = match[3].strip()
        if text:
            events.append({"start_s": start_s, "end_s": end_s, "text": text})

    return events, "SRT/TXT Raw Format"


def auto_generate_lyrics(events):
    """توليد ملف كلمات تلقائي وتجميع الأحرف المقطعة في أسطر إذا لم يُوفر ملف كلمات جاهز"""
    lines = []
    current_tokens = []

    for ev in events:
        raw_t = ev["text"]
        has_tag = "[" in raw_t or "]" in raw_t
        clean_t = re.sub(r"\[.*?\]", "", raw_t)
        clean_t = re.sub(r"\(.*?\)", "", clean_t).strip()

        if has_tag and current_tokens:
            line_str = " ".join(current_tokens)
            line_str = re.sub(r"(?<=\S)\s+(?=\S)", "", line_str)
            if line_str.strip():
                lines.append(line_str.strip())
            current_tokens = []

        if clean_t:
            current_tokens.append(clean_t)

    if current_tokens:
        line_str = " ".join(current_tokens)
        lines.append(line_str.strip())

    return [l for l in lines if len(l) > 3]


def format_srt_time(seconds):
    """تحويل الثواني إلى صيغة SRT القياسية 00:00:00,000"""
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    ms = int(round((seconds % 1) * 1000))
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{ms:03d}"


def process_song(raw_filepath, lyrics_filepath=None):
    """المحرك الرئيسي للمطابقة والتشخيص"""
    print("=" * 65)
    print("🚀 بدء معالجة الأغنية وتشغيل نظام المطابقة والتشخيص...")
    print("=" * 65)

    if not os.path.exists(raw_filepath):
        print(f"❌ خطأ: ملف التوقيت الخام غير موجود: {raw_filepath}")
        return

    raw_events, input_type = parse_raw_input(raw_filepath)
    print(f"📄 نوع ملف التوقيت المكتشف: [{input_type}]")
    print(f"📊 إجمالي الكتل الزمنية الخام: {len(raw_events)}")

    # إذا لم يُحدد ملف كلمات أو لم يكن موجوداً، إنشاؤه تلقائياً
    if not lyrics_filepath or not os.path.exists(lyrics_filepath):
        if not lyrics_filepath:
            base_name = os.path.splitext(raw_filepath)[0]
            lyrics_filepath = f"{base_name}.txt"

        print(f"⚠️ ملف الكلمات '{lyrics_filepath}' غير موجود.")
        print("💡 جارٍ استخراج وإنشاء ملف الكلمات تلقائياً من التوقيتات الخام...")

        auto_lines = auto_generate_lyrics(raw_events)
        with open(lyrics_filepath, "w", encoding="utf-8") as f:
            f.write("\n\n".join(auto_lines))
        print(f"✅ تم إنشاء ملف الكلمات تلقائياً وحفظه في: [{lyrics_filepath}]")

    with open(lyrics_filepath, "r", encoding="utf-8") as f:
        lyrics_content = f.read()

    # استخراج أبيات القصيدة النظيفة
    raw_lines = lyrics_content.strip().split("\n")
    clean_lines = []
    for line in raw_lines:
        line_clean = re.sub(r"\[.*?\]", "", line)
        line_clean = re.sub(r"\(.*?\)", "", line_clean).strip()
        if line_clean:
            clean_lines.append(line_clean)

    print(f"📝 إجمالي الأسطر/الأبيات في نص الأغنية: {len(clean_lines)}")
    print("-" * 65)

    processed_events = []
    for ev in raw_events:
        clean_t = re.sub(r"\[.*?\]", "", ev["text"])
        clean_t = re.sub(r"\(.*?\)", "", clean_t).strip()
        norm = normalize_text(clean_t)
        if norm:
            processed_events.append(
                {
                    "start_s": ev["start_s"],
                    "end_s": ev["end_s"],
                    "norm": norm,
                    "char_count": len(norm),
                }
            )

    output_subtitles = []
    diagnostics = []
    event_ptr = 0
    total_events = len(processed_events)

    for line_idx, line_text in enumerate(clean_lines, 1):
        target_norm = normalize_text(line_text)
        target_len = len(target_norm)

        if target_len == 0:
            continue

        if event_ptr >= total_events:
            diagnostics.append(
                {
                    "line": line_idx,
                    "text": line_text,
                    "status": "FAILED_OUT_OF_EVENTS",
                    "msg": "⚠️ انتهت التوقيتات الخام قبل الوصول لهذا السطر.",
                }
            )
            continue

        line_start = processed_events[event_ptr]["start_s"]
        line_end = processed_events[event_ptr]["end_s"]
        accumulated_chars = 0
        consumed_events_count = 0

        while event_ptr < total_events and accumulated_chars < target_len:
            ev = processed_events[event_ptr]
            line_end = ev["end_s"]
            accumulated_chars += ev["char_count"]
            event_ptr += 1
            consumed_events_count += 1

        output_subtitles.append(
            {
                "index": len(output_subtitles) + 1,
                "start_str": format_srt_time(line_start),
                "end_str": format_srt_time(line_end),
                "start_s": line_start,
                "end_s": line_end,
                "text": line_text,
            }
        )

        char_diff = abs(accumulated_chars - target_len)
        match_quality = (
            "EXCELLENT" if char_diff <= 2 else ("GOOD" if char_diff <= 5 else "WARNING")
        )

        diagnostics.append(
            {
                "line": line_idx,
                "text": line_text,
                "status": match_quality,
                "start": format_srt_time(line_start),
                "end": format_srt_time(line_end),
                "duration": round(line_end - line_start, 2),
                "target_chars": target_len,
                "matched_chars": accumulated_chars,
                "events_used": consumed_events_count,
            }
        )

    print("\n🔍 --- تقرير التشخيص والتطابق (DIAGNOSTIC REPORT) ---")
    warnings_count = 0

    for diag in diagnostics:
        status_symbol = "✅" if diag["status"] in ["EXCELLENT", "GOOD"] else "⚠️"
        if diag["status"] not in ["EXCELLENT", "GOOD"]:
            warnings_count += 1

        if "start" in diag:
            print(
                f"{status_symbol} [سطر {diag['line']:02d}] ({diag['start']} --> {diag['end']}) | المدة: {diag['duration']}ث"
            )
            print(f"   البيت: {diag['text']}")
            print(
                f"   التطابق: {diag['matched_chars']}/{diag['target_chars']} حرف (استهلاك {diag['events_used']} كتل زمنية)"
            )
        else:
            print(f"❌ [سطر {diag['line']:02d}] {diag['msg']}")
            print(f"   البيت: {diag['text']}")
        print("-" * 50)

    leftover_events = total_events - event_ptr
    if leftover_events > 0:
        print(
            f"ℹ️ ملاحظة تشخيصية: تبقى {leftover_events} كتلة زمنية في نهاية الملف لم تُستخدم."
        )

    output_srt_path = "cleaned_subtitles.srt"
    srt_blocks = []
    for sub in output_subtitles:
        srt_blocks.append(
            f"{sub['index']}\n{sub['start_str']} --> {sub['end_str']}\n{sub['text']}"
        )

    with open(output_srt_path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(srt_blocks))

    print("\n" + "=" * 65)
    print(f"🎉 تم الانتهاء! ملف الترجمة النظيف جاهز: [{output_srt_path}]")
    print(
        f"📊 نتيجة التشخيص: {len(output_subtitles)}/{len(clean_lines)} أسطر تم مطابقتها ({warnings_count} تحذيرات)."
    )
    print("=" * 65)


if __name__ == "__main__":
    raw_file = "suno_raw.txt"
    lyrics_file = None

    if len(sys.argv) >= 2:
        raw_file = sys.argv[1]
    if len(sys.argv) >= 3:
        lyrics_file = sys.argv[2]

    process_song(raw_file, lyrics_file)
