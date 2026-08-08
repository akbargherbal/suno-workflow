"""
Suno-Style Annotated Lyrics Pipeline
=====================================
يحوّل ملف صوتي غنائي إلى نص كلمات منسق بأسلوب Suno:
[Verse]/[Chorus]/[Bridge] + وصف الآلات والإنتاج بين الأسطر.

مصمم للعمل على Google Colab مع GPU (T4 أو L4).

الخطوات:
1) Demucs           -> فصل الصوت الغنائي عن الموسيقى
2) faster-whisper   -> تفريغ الكلمات مع توقيتات (يدعم العربية)
3) librosa+sklearn  -> تقسيم بنية الأغنية تقريبيًا (intro/verse/chorus/outro)
   (بديل عن all-in-one/madmom اللي غير مستقرة مع بايثون/numpy الحديثة)
4) PANNs            -> تصنيف/كشف الآلات النشطة في كل مقطع (خفيف، لا يحتاج نموذج ضخم)
5) (اختياري) Qwen2-Audio -> وصف نصي حر للإنتاج الصوتي (يحتاج GPU 16GB+، أفضل مع L4)
6) دمج كل شيء بفورمات نصي شبيه بمخرجات Suno

كيفية الاستخدام في Colab:
    !pip install -q -r requirements  (انظر خلية التثبيت أدناه)
    من قائمة Runtime اختر GPU (T4 أو L4) قبل التشغيل
    python suno_style_lyrics_pipeline.py --audio song.mp3 --lang ar
"""

import argparse
import json
import os
import subprocess
import sys

# ----------------------------------------------------------------------
# 1) التثبيت (شغّلها مرة وحدة في خلية Colab منفصلة، مو داخل السكربت):
#
# !pip install -q demucs faster-whisper panns-inference torch torchaudio
# !pip install -q librosa scikit-learn scipy huggingface_hub
# !pip install -q transformers accelerate soundfile  # لازم فقط لو رح تستخدم Qwen2-Audio
#
# ----------------------------------------------------------------------


def separate_vocals(audio_path: str, out_dir: str = "separated") -> dict:
    """يفصل الصوت الغنائي عن الموسيقى باستخدام Demucs."""
    print("[1/5] فصل المسارات (Demucs)...")
    subprocess.run(
        ["demucs", "--two-stems=vocals", "-o", out_dir, audio_path],
        check=True,
    )
    stem = os.path.splitext(os.path.basename(audio_path))[0]
    model_dir = os.path.join(out_dir, "htdemucs", stem)
    return {
        "vocals": os.path.join(model_dir, "vocals.wav"),
        "instrumental": os.path.join(model_dir, "no_vocals.wav"),
    }


def transcribe(vocals_path: str, lang: str = "ar") -> list:
    """تفريغ الكلمات مع توقيتات باستخدام faster-whisper (يدعم العربية)."""
    print("[2/5] تفريغ الكلمات (faster-whisper large-v3)...")
    from faster_whisper import WhisperModel

    model = WhisperModel("large-v3", device="cuda", compute_type="float16")
    segments, _ = model.transcribe(
        vocals_path, language=lang, word_timestamps=True, vad_filter=True
    )
    lines = []
    for seg in segments:
        lines.append({"start": seg.start, "end": seg.end, "text": seg.text.strip()})
    return lines


def analyze_structure(audio_path: str, sr_target: int = 22050) -> list:
    """
    تقسيم بنية الأغنية إلى intro/verse/chorus/outro بدون أي تبعية على
    madmom/allin1 (غير مستقرة). يعتمد فقط على librosa + scikit-learn:

    1) استخراج ميزات chroma + mfcc متزامنة مع النبضات (beats)
    2) بناء self-similarity matrix واستخراج منحنى "novelty" لتحديد حدود المقاطع
    3) تجميع المقاطع المتشابهة بعناقيد (clustering) لتخمين أيها "chorus" (الأكثر تكرارًا)

    النتيجة تقريبية دلاليًا (زي "chorus"/"verse") لكنها مستقرة تقنيًا 100%.
    """
    print("[3/5] تحليل بنية الأغنية (librosa self-similarity + clustering)...")
    import numpy as np
    import librosa
    from scipy.signal import find_peaks
    from sklearn.cluster import AgglomerativeClustering
    from collections import Counter

    y, sr = librosa.load(audio_path, sr=sr_target)
    duration = librosa.get_duration(y=y, sr=sr)

    def _fixed_fallback(step: float = 8.0) -> list:
        bounds = list(np.arange(0, duration, step)) + [duration]
        return [
            {"start": float(bounds[i]), "end": float(bounds[i + 1]), "label": "verse"}
            for i in range(len(bounds) - 1)
        ]

    _, beat_frames = librosa.beat.beat_track(y=y, sr=sr, trim=False)
    if len(beat_frames) < 8:
        return _fixed_fallback()

    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
    chroma_sync = librosa.util.sync(chroma, beat_frames, aggregate=np.median)
    mfcc_sync = librosa.util.sync(mfcc, beat_frames, aggregate=np.mean)
    features = np.vstack([chroma_sync, mfcc_sync]).T  # (n_beats, n_features)

    beat_times = librosa.frames_to_time(beat_frames, sr=sr)
    beat_times = np.append(beat_times, duration)

    # self-similarity + novelty curve لتحديد حدود المقاطع
    R = librosa.segment.recurrence_matrix(features.T, mode="affinity", sym=True, width=3)
    novelty = np.sum(np.abs(np.diff(R, axis=0)), axis=1)
    # مسافة دنيا أكبر بين الحدود لتقليل التقطيع المبالغ فيه (~12 ثانية تقريبًا بدل القديم)
    min_distance = max(8, len(novelty) // 10)
    # نأخذ فقط القمم الأوضح (فوق المتوسط + انحراف معياري) بدل كل القمم
    peak_height = novelty.mean() + 0.5 * novelty.std()
    peaks, _ = find_peaks(novelty, distance=min_distance, height=peak_height)
    boundaries = sorted(set([0] + list(peaks) + [len(features) - 1]))

    # دمج الحدود القريبة جدًا (أقل من 10 ثواني) لتفادي مقاطع مجهرية
    merged = [boundaries[0]]
    for b in boundaries[1:]:
        if beat_times[b] - beat_times[merged[-1]] > 10.0:
            merged.append(b)
    boundaries = merged

    if len(boundaries) < 3:
        return _fixed_fallback()

    seg_feats = np.array(
        [features[boundaries[i]:boundaries[i + 1]].mean(axis=0) for i in range(len(boundaries) - 1)]
    )

    n_clusters = min(4, len(seg_feats))
    if n_clusters >= 2:
        cluster_labels = AgglomerativeClustering(n_clusters=n_clusters).fit_predict(seg_feats)
    else:
        cluster_labels = np.zeros(len(seg_feats), dtype=int)

    # العنقود الأكثر تكرارًا نخمّنه "chorus" (لأن الكورس عادة يتكرر لحنيًا)
    chorus_cluster = Counter(cluster_labels).most_common(1)[0][0]

    segments = []
    n_segs = len(boundaries) - 1
    for i in range(n_segs):
        start = float(beat_times[boundaries[i]])
        end = float(beat_times[boundaries[i + 1]])
        if i == 0:
            label = "intro"
        elif i == n_segs - 1:
            label = "outro"
        elif cluster_labels[i] == chorus_cluster:
            label = "chorus"
        else:
            label = "verse"
        segments.append({"start": start, "end": end, "label": label})

    return segments


def normalize_arabic(text: str) -> str:
    """تطبيع نص عربي للمقارنة: إزالة التشكيل وتوحيد أشكال الحروف المتقاربة."""
    import re

    text = re.sub(r"[\u0610-\u061A\u064B-\u065F\u06D6-\u06ED\u08D4-\u08E1\u08E3-\u08FF]", "", text)
    text = re.sub(r"[إأآا]", "ا", text)
    text = re.sub(r"ى", "ي", text)
    text = re.sub(r"ة", "ه", text)
    text = re.sub(r"ؤ", "و", text)
    text = re.sub(r"ئ", "ي", text)
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def load_reference_poem(poem_py_path: str) -> list:
    """يحمّل قائمة الأبيات المرجعية (النص الصحيح المشكَّل) من ملف poem.py (متغيّر poem_list)."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("poem_ref", poem_py_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    flat = []
    for bait in mod.poem_list:
        flat.extend(bait)  # كل بيت = شطرين (hemistich) -> نفردهم بقائمة واحدة
    return flat


def align_lyrics_to_reference(asr_lines: list, reference_lines: list) -> list:
    """
    يطابق كل سطر متعرَّف عليه (ASR) بشكل مستقل مع أقرب بيت/شطر من النص
    المرجعي الصحيح، بدل الاعتماد على محاذاة تسلسلية صارمة.

    السبب: الأغنية غالبًا تكرر أبياتًا سابقة (كورس = تكرار)، وأي محاذاة
    تسلسلية (زي diff عادي) تنكسر بمجرد أول تكرار لأن المرجع لا يحتوي على
    نفس التكرار بنفس الموضع - فتبدأ "تتوه" وتخطئ لبقية النص. المطابقة
    المستقلة (nearest-neighbor) تتجنب هالمشكلة لأن كل سطر يُحلّ لوحده.

    نبني أيضًا مرشحين على مستوى "البيت الكامل" (شطرين مدموجين) لأن Whisper
    أحيانًا يدمج شطرين بجملة/segment واحدة.
    """
    import difflib

    candidates = [(normalize_arabic(line), line) for line in reference_lines]
    for i in range(0, len(reference_lines) - 1, 2):
        merged = reference_lines[i] + " " + reference_lines[i + 1]
        candidates.append((normalize_arabic(merged), merged))

    corrected = []
    for line in asr_lines:
        norm = normalize_arabic(line["text"])
        scored = []
        for cand_norm, cand_orig in candidates:
            if not cand_norm:
                continue
            ratio = difflib.SequenceMatcher(None, norm, cand_norm).ratio()
            scored.append((ratio, cand_orig))
        scored.sort(key=lambda x: x[0], reverse=True)

        new_line = dict(line)
        if scored:
            best_ratio, best_text = scored[0]
            second_ratio = scored[1][0] if len(scored) > 1 else 0.0
            # نقبل الاستبدال فقط لو التطابق قوي بوضوح، ومتفوّق بهامش واضح
            # عن ثاني أفضل مرشح - عشان نتفادى استبدال سطر مشوّش ببيت بعيد
            # من القصيدة تصادف تشابهه شكليًا (false positive).
            if best_ratio > 0.55 and (best_ratio - second_ratio) > 0.05:
                new_line["text"] = best_text
        # وإلا (زي ad-libs "ah-ah-ah" أو تطابق غامض) نترك نص ASR كما هو
        corrected.append(new_line)

    return corrected


def tag_instruments(instrumental_path: str, segments: list) -> dict:
    """كشف الآلات النشطة في كل مقطع زمني باستخدام PANNs (AudioSet tags)."""
    print("[4/5] تصنيف الآلات لكل مقطع (PANNs)...")
    from panns_inference import AudioTagging, labels
    import librosa
    import numpy as np

    # نحمّل الـ checkpoint من مرآة HuggingFace (CDN سريع) بدل Zenodo
    # الافتراضي (بطيء جدًا وأحيانًا مقيّد السرعة). نفس الملف، نفس checksum.
    ckpt_path = os.path.join(os.path.expanduser("~"), "panns_data", "Cnn14_mAP=0.431.pth")
    if not os.path.exists(ckpt_path):
        print("      تحميل PANNs checkpoint من HuggingFace (أسرع من Zenodo)...")
        from huggingface_hub import hf_hub_download

        os.makedirs(os.path.dirname(ckpt_path), exist_ok=True)
        downloaded = hf_hub_download(
            repo_id="thelou1s/panns-inference",
            filename="Cnn14_mAP=0.431.pth",
        )
        # panns_inference يتوقع الملف في ~/panns_data/ بالضبط
        if not os.path.exists(ckpt_path):
            os.symlink(downloaded, ckpt_path)

    # فئات عامة جدًا تطلع بكل مقطع تقريبًا بغض النظر عن المحتوى الفعلي - نستبعدها
    GENERIC_TAGS = {"music", "musical instrument", "speech", "sound effect", "singing"}

    at = AudioTagging(checkpoint_path=ckpt_path, device="cuda")
    y, sr = librosa.load(instrumental_path, sr=32000)

    tags_per_segment = {}
    for seg in segments:
        s_sample = int(seg["start"] * sr)
        e_sample = int(seg["end"] * sr)
        chunk = y[s_sample:e_sample]
        if len(chunk) < sr:  # مقطع قصير جدًا
            continue
        clipwise_output, _ = at.inference(chunk[None, :])
        top_idx = np.argsort(clipwise_output[0])[-15:][::-1]
        top_tags = [
            labels[i] for i in top_idx
            if clipwise_output[0][i] > 0.08 and labels[i].lower() not in GENERIC_TAGS
        ][:4]
        tags_per_segment[(seg["start"], seg["end"])] = top_tags
    return tags_per_segment


def describe_with_qwen_audio(instrumental_path: str, segments: list) -> dict:
    """(اختياري) وصف نصي حر للإنتاج الصوتي - يحتاج GPU 16GB+ (أفضل مع L4)."""
    print("[اختياري] وصف الإنتاج الصوتي (Qwen2-Audio)...")
    from transformers import Qwen2AudioForConditionalGeneration, AutoProcessor
    import soundfile as sf

    model_id = "Qwen/Qwen2-Audio-7B-Instruct"
    processor = AutoProcessor.from_pretrained(model_id)
    model = Qwen2AudioForConditionalGeneration.from_pretrained(
        model_id, device_map="cuda", torch_dtype="auto"
    )

    y, sr = sf.read(instrumental_path)
    descriptions = {}
    for seg in segments:
        s, e = int(seg["start"] * sr), int(seg["end"] * sr)
        chunk = y[s:e]
        if len(chunk) < sr:
            continue
        prompt = "صف بإيجاز الآلات الموسيقية وطابع الإنتاج الصوتي في هذا المقطع."
        inputs = processor(text=prompt, audios=chunk, sampling_rate=sr, return_tensors="pt").to("cuda")
        out = model.generate(**inputs, max_new_tokens=40)
        text = processor.decode(out[0], skip_special_tokens=True)
        descriptions[(seg["start"], seg["end"])] = text
    return descriptions


def build_suno_format(segments, lyrics_lines, instrument_tags, qwen_desc=None) -> str:
    """يدمج كل النتائج بفورمات نصي شبيه بمخرجات Suno."""
    print("[5/5] بناء المخرج النهائي...")

    # نجهّز أول: نربط كل مقطع بأسطره الغنائية، ونستبعد المقاطع الفارغة تمامًا
    prepared = []
    for seg in segments:
        seg_lines = [
            line["text"] for line in lyrics_lines
            if seg["start"] <= line["start"] < seg["end"]
        ]
        if seg_lines:  # نتجاهل المقاطع اللي ما فيها أي كلام (غالبًا ضوضاء تقسيم)
            prepared.append({**seg, "lines": seg_lines})

    # ندمج المقاطع المتتالية بنفس التصنيف (verse تلو verse، chorus تلو chorus)
    merged = []
    for seg in prepared:
        if merged and merged[-1]["label"] == seg["label"]:
            merged[-1]["end"] = seg["end"]
            merged[-1]["lines"].extend(seg["lines"])
        else:
            merged.append(dict(seg))

    out = []
    for seg in merged:
        out.append(f"[{seg['label'].capitalize()}]")

        key = (seg["start"], seg["end"])
        if qwen_desc and key in qwen_desc:
            out.append(f"[{qwen_desc[key]}]")
        else:
            # نبحث عن أقرب مقطع أصلي متداخل عشان نجيب له تاقات الآلات
            tags = []
            for (s, e), t in instrument_tags.items():
                if s < seg["end"] and e > seg["start"] and t:
                    tags = t
                    break
            if tags:
                out.append(f"[{', '.join(tags)}]")

        out.extend(seg["lines"])
        out.append("")
    return "\n".join(out)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio", required=True, help="مسار الملف الصوتي")
    parser.add_argument("--lang", default="ar", help="لغة الكلمات (ar/en/...)")
    parser.add_argument("--use-qwen", action="store_true", help="استخدام Qwen2-Audio لوصف أغنى (يحتاج L4 أو GPU أقوى)")
    parser.add_argument(
        "--reference-poem",
        default=None,
        help="مسار ملف poem.py يحتوي على poem_list (النص المرجعي الصحيح المشكَّل) لتصحيح مخرجات ASR تلقائيًا",
    )
    parser.add_argument("--out", default="lyrics_output.txt")
    args = parser.parse_args()

    stems = separate_vocals(args.audio)
    lyrics = transcribe(stems["vocals"], lang=args.lang)

    if args.reference_poem:
        print("[+] محاذاة النص مع المرجع الصحيح (poem.py)...")
        reference_lines = load_reference_poem(args.reference_poem)
        lyrics = align_lyrics_to_reference(lyrics, reference_lines)

    structure = analyze_structure(args.audio)
    inst_tags = tag_instruments(stems["instrumental"], structure)

    qwen_desc = None
    if args.use_qwen:
        qwen_desc = describe_with_qwen_audio(stems["instrumental"], structure)

    result_text = build_suno_format(structure, lyrics, inst_tags, qwen_desc)

    with open(args.out, "w", encoding="utf-8") as f:
        f.write(result_text)

    print(f"\n✅ تم الحفظ في: {args.out}\n")
    print(result_text)


if __name__ == "__main__":
    main()
