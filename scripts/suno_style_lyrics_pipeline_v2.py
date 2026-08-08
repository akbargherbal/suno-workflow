"""
Suno-Style Annotated Lyrics Pipeline — v2 (محسّنة)
====================================================
تحسينات عن النسخة الأولى (بناءً على تشخيص فجوة الجودة مع مخرجات Suno الفعلية):

  1) وسوم إنتاج حرة (production-direction tags) بدل تصنيف PANNs العام:
     - نجعل Qwen2-Audio هو المصدر الافتراضي (مش اختياري) مع prompt يطلب
       تحديدًا صياغة بأسلوب وسم إنتاج قصير ("distorted electric guitar
       power chords enter") بدل وصف حر طويل.
     - لو GPU ما يكفي لـ Qwen2-Audio، نسقط تلقائيًا (fallback) على PANNs
       + قاموس تحويل (mapping) من تصنيفات AudioSet العامة لصياغة أقرب
       لأسلوب Suno، بدل طباعة اسم الصنف الخام زي "New-age music".

  2) تجزئة بنية أدق:
     - "solo": مقطع ما فيه أي كلام غنائي (ASR فاضي) رغم انه مو أول ولا
       آخر مقطع بالأغنية -> الأرجح انه guitar solo / instrumental break.
     - "bridge": بدل افتراض ان العنقود الأكثر تكرارًا هو الكورس دايمًا،
       نرتب العناقيد حسب التكرار: الأكثر تكرارًا = chorus، عنقود متوسط
       التكرار يظهر مرة وحدة تقريبًا فى منتصف الأغنية = bridge.

  3) محاذاة أدق (align_lyrics_to_reference):
     - أي سطر ASR ما طابق بيت/شطر كامل بثقة كافية، بدل ما نتركه خام
       (وهذا كان يطلع أسطر مشوهة زي "ردت علي ضرب الوليدة بالمسحات في
       الثأد")، نحاول محاذاة على مستوى الكلمة: نقسم السطر لكلمات ونطابق
       كل كلمة لأقرب كلمة بالمرجع (بمسافة تحريرية / Levenshtein)، ثم
       نعيد تركيب السطر من الكلمات المرجعية المطابقة. هذا يلتقط حالة
       "Whisper دمج نص من بيتين مختلفين بجملة وحدة".

  4) إزالة تكرار بالعرض النهائي:
     - القسم الواحد (خصوصًا الكورس) ما يعرض نفس السطر أكثر من مرتين
       متتاليتين، حتى لو ASR كرره فعليًا أكثر من كذا زمنيًا.

باقي الخطوات (Demucs / faster-whisper / librosa+sklearn للحدود الزمنية)
نفس المنطق الأساسي للنسخة الأولى.
"""

import argparse
import os
import subprocess

# ----------------------------------------------------------------------
# التثبيت (شغّلها مرة وحدة بخلية Colab منفصلة):
#
# !pip install -q demucs faster-whisper panns-inference torch torchaudio
# !pip install -q librosa scikit-learn scipy huggingface_hub python-Levenshtein
# !pip install -q transformers accelerate soundfile   # لازم لـ Qwen2-Audio (الافتراضي الآن)
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


def analyze_structure(audio_path: str, asr_lines: list, sr_target: int = 22050) -> list:
    """
    تقسيم بنية الأغنية إلى intro/verse/chorus/bridge/solo/outro.

    تحسين v2: بدل افتراض "العنقود الأكثر تكرارًا = chorus" فقط، نرتب كل
    العناقيد حسب عدد مرات ظهورها، ونضيف تصنيف solo لأي مقطع لا يحتوي على
    أي كلام غنائي متداخل زمنيًا معه (رغم انه مش أول/آخر مقطع).
    """
    print("[3/5] تحليل بنية الأغنية (librosa self-similarity + clustering)...")
    import numpy as np
    import librosa
    from scipy.signal import find_peaks
    from sklearn.cluster import AgglomerativeClustering
    from collections import Counter

    y, sr = librosa.load(audio_path, sr=sr_target)
    duration = librosa.get_duration(y=y, sr=sr)

    def _has_vocals(start: float, end: float) -> bool:
        return any(start <= ln["start"] < end and ln["text"].strip() for ln in asr_lines)

    def _fixed_fallback(step: float = 8.0) -> list:
        bounds = list(np.arange(0, duration, step)) + [duration]
        return [
            {
                "start": float(bounds[i]),
                "end": float(bounds[i + 1]),
                "label": "verse" if _has_vocals(bounds[i], bounds[i + 1]) else "solo",
            }
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

    R = librosa.segment.recurrence_matrix(features.T, mode="affinity", sym=True, width=3)
    novelty = np.sum(np.abs(np.diff(R, axis=0)), axis=1)
    min_distance = max(8, len(novelty) // 10)
    peak_height = novelty.mean() + 0.5 * novelty.std()
    peaks, _ = find_peaks(novelty, distance=min_distance, height=peak_height)
    boundaries = sorted(set([0] + list(peaks) + [len(features) - 1]))

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

    # ترتيب العناقيد حسب التكرار تنازليًا: الأكثر تكرارًا = chorus،
    # العنقود التالي (لو ظهر أكثر من مرة وبمنتصف الأغنية) = bridge محتمل
    counts = Counter(cluster_labels)
    ranked_clusters = [c for c, _ in counts.most_common()]
    chorus_cluster = ranked_clusters[0] if ranked_clusters else None
    bridge_cluster = (
        ranked_clusters[1] if len(ranked_clusters) > 1 and counts[ranked_clusters[1]] >= 2 else None
    )

    segments = []
    n_segs = len(boundaries) - 1
    for i in range(n_segs):
        start = float(beat_times[boundaries[i]])
        end = float(beat_times[boundaries[i + 1]])

        if not _has_vocals(start, end) and 0 < i < n_segs - 1:
            label = "solo"
        elif i == 0:
            label = "intro"
        elif i == n_segs - 1:
            label = "outro"
        elif cluster_labels[i] == chorus_cluster:
            label = "chorus"
        elif bridge_cluster is not None and cluster_labels[i] == bridge_cluster:
            label = "bridge"
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
        flat.extend(bait)
    return flat


def _levenshtein(a: str, b: str) -> int:
    """مسافة تحريرية بسيطة (dynamic programming) بدون تبعية خارجية."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            curr[j] = min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost)
        prev = curr
    return prev[-1]


def _word_level_reconstruct(asr_text: str, reference_lines: list) -> tuple:
    """
    تحسين v2: لو السطر كامل ما طابق أي بيت/شطر مرجعي بثقة كافية (حالة
    دمج Whisper لبيتين مختلفين بجملة واحدة)، نحاول تركيب السطر كلمة
    كلمة: كل كلمة من ASR تُستبدل بأقرب كلمة (Levenshtein) موجودة في مجمع
    كلمات القصيدة كاملة. لو ما لقينا كلمة قريبة بشكل معقول، نُبقي كلمة
    ASR كما هي بدل حذفها (تفادي فقدان معنى).

    تحسين v4: يرجّع أيضًا `confidence` = نسبة الكلمات اللي انضبط استبدالها
    بثقة (مقارنة بإجمالي كلمات السطر). هذا يسمح لـ align_lyrics_to_reference
    يميّز بين إعادة بناء موثوقة (نعرضها كما هي) وإعادة بناء ضعيفة جدًا
    (يفضّل نعرض بدلها تخمين البيت المتوقع مع علامة [?] بدل نص مشوّه).
    """
    vocab = set()
    for line in reference_lines:
        vocab.update(line.split())

    words = asr_text.split()
    if not words or not vocab:
        return asr_text, 0.0

    rebuilt = []
    matched_count = 0
    for w in words:
        w_norm = normalize_arabic(w)
        if not w_norm:
            rebuilt.append(w)
            continue
        best_word, best_dist = None, None
        for cand in vocab:
            cand_norm = normalize_arabic(cand)
            if not cand_norm:
                continue
            # فلترة سريعة: تجاهل مرشحين بفرق طول كبير قبل حساب Levenshtein
            if abs(len(cand_norm) - len(w_norm)) > 3:
                continue
            d = _levenshtein(w_norm, cand_norm)
            if best_dist is None or d < best_dist:
                best_dist, best_word = d, cand
        # نقبل الاستبدال فقط لو الفرق صغير نسبيًا لطول الكلمة (≈ خطأ إملائي/نطقي)
        if best_word is not None and best_dist <= max(1, len(w_norm) // 3):
            rebuilt.append(best_word)
            matched_count += 1
        else:
            rebuilt.append(w)
    confidence = matched_count / len(words)
    return " ".join(rebuilt), confidence


def align_lyrics_to_reference(asr_lines: list, reference_lines: list) -> list:
    """
    يطابق كل سطر ASR بشكل مستقل مع أقرب بيت/شطر مرجعي (nearest-neighbor)
    بدل محاذاة تسلسلية تنكسر مع أول تكرار (كورس).

    تحسين v2: لو ما فيه مرشح بثقة كافية على مستوى السطر الكامل، نحاول
    إعادة تركيب على مستوى الكلمة (_word_level_reconstruct) بدل ترك نص
    ASR الخام كما هو، لأن هذا هو مصدر الأسطر المشوهة في مخرجات v1.

    تحسين v3: كل سطر يُطابَق نُرفق له `bait_id` (رقم البيت الشعري الكامل
    اللي ينتمي له الشطر بملف poem.py، بيت = شطرين متتاليين). هذا يسمح
    لاحقًا (build_suno_format) بمنع تقسيم نفس البيت بين قسمين مختلفين
    (Verse/Chorus) لمجرد إن حد زمني وقع بالصدفة بمنتصف البيت.

    تحسين v4: لو حتى إعادة البناء كلمة-بكلمة طلعت بثقة ضعيفة جدًا (يعني
    Whisper سمع المقطع بشكل سيء لدرجة ما نقدر نعيد بناءه بشكل موثوق)،
    بدل عرض نص مشوّه كأنه تفريغ مؤكد، نعرض بدلاً منه الشطر المرجعي
    المتوقع التالي (حسب ترتيب القصيدة بعد آخر شطر تعرّفنا عليه بثقة)
    مع علامة `[?] ` صريحة تدل إنه تخمين موضعي مو تفريغ فعلي.
    """
    import difflib

    WORD_LEVEL_CONFIDENCE_THRESHOLD = 0.5  # أقل من هالنسبة = إعادة البناء غير موثوقة

    # كل مرشح مربوط بـ: bait_id (رقم البيت) و end_ref_idx (مؤشر آخر شطر
    # يغطيه المرشح ضمن reference_lines، يُستخدم لتخمين "الشطر التالي المتوقع")
    candidates = [
        (normalize_arabic(reference_lines[i]), reference_lines[i], i // 2, i)
        for i in range(len(reference_lines))
    ]
    for i in range(0, len(reference_lines) - 1, 2):
        merged_line = reference_lines[i] + " " + reference_lines[i + 1]
        candidates.append((normalize_arabic(merged_line), merged_line, i // 2, i + 1))

    corrected = []
    last_confident_ref_idx = None  # آخر مؤشر شطر (بـ reference_lines) تعرّفنا عليه بثقة

    for line in asr_lines:
        norm = normalize_arabic(line["text"])
        scored = []
        for cand_norm, cand_orig, cand_bait_id, cand_end_idx in candidates:
            if not cand_norm:
                continue
            ratio = difflib.SequenceMatcher(None, norm, cand_norm).ratio()
            scored.append((ratio, cand_orig, cand_bait_id, cand_end_idx))
        scored.sort(key=lambda x: x[0], reverse=True)

        new_line = dict(line)
        new_line["bait_id"] = None
        new_line["guessed"] = False

        if not line["text"].strip():
            corrected.append(new_line)
            continue

        best_ratio, second_ratio = 0.0, 0.0
        best_text = best_bait_id = best_end_idx = None
        if scored:
            best_ratio, best_text, best_bait_id, best_end_idx = scored[0]
            second_ratio = scored[1][0] if len(scored) > 1 else 0.0

        if best_ratio > 0.55 and (best_ratio - second_ratio) > 0.05:
            new_line["text"] = best_text
            new_line["bait_id"] = best_bait_id
            last_confident_ref_idx = best_end_idx
        else:
            # لا يوجد مرشح واثق على مستوى السطر الكامل -> محاولة كلمة-بكلمة
            rebuilt_text, word_confidence = _word_level_reconstruct(line["text"], reference_lines)
            # فحص إضافي: نسبة الكلمات المطابقة وحدها مو كافية، لأن مفردات
            # القصيدة الكبيرة ممكن تعطي تشابه صدفة لكلمات من أبيات مختلفة
            # (زي كلمة تشبه "أجود" بينما الأصل "أُجُدِ" من بيت ثاني تمامًا).
            # نتأكد كمان إن السطر المُعاد بناؤه ككل يشبه بيتًا حقيقيًا واحدًا.
            rebuilt_norm = normalize_arabic(rebuilt_text)
            best_line_ratio = max(
                (difflib.SequenceMatcher(None, rebuilt_norm, cn).ratio() for cn, *_ in candidates if cn),
                default=0.0,
            )
            if word_confidence >= WORD_LEVEL_CONFIDENCE_THRESHOLD and best_line_ratio >= 0.6:
                new_line["text"] = rebuilt_text
                # bait_id يبقى None لأننا مو متأكدين لأي بيت ينتمي هالسطر بثقة كافية
            elif last_confident_ref_idx is not None and last_confident_ref_idx + 1 < len(reference_lines):
                # ثقة ضعيفة جدًا حتى بإعادة البناء -> نخمّن الشطر التالي المتوقع
                guessed_idx = last_confident_ref_idx + 1
                new_line["text"] = "[?] " + reference_lines[guessed_idx]
                new_line["bait_id"] = guessed_idx // 2
                new_line["guessed"] = True
                last_confident_ref_idx = guessed_idx
            else:
                # ما فيه حتى تخمين ممكن (أول الأغنية مثلًا) -> نُبقي أفضل ما نقدر
                new_line["text"] = rebuilt_text

        corrected.append(new_line)

    return corrected



# قاموس تحويل احتياطي: من تصنيفات AudioSet/PANNs العامة إلى صياغة أقرب
# لأسلوب وسوم الإنتاج بـ Suno. يُستخدم فقط لو Qwen2-Audio غير متاح.
_PANNS_TO_PRODUCTION_STYLE = {
    "electric guitar": "electric guitar riff enters",
    "distortion": "distorted electric guitar power chords",
    "acoustic guitar": "clean acoustic guitar arpeggio",
    "drum kit": "full drum kit driving the rhythm",
    "bass drum": "heavy kick drum accents",
    "orchestra": "orchestral strings swell",
    "string section": "orchestral strings swell",
    "synthesizer": "synth pad enters",
    "male singing": "baritone male vocals",
    "female singing": "female lead vocals",
}


def tag_instruments(instrumental_path: str, segments: list) -> dict:
    """
    كشف الآلات النشطة في كل مقطع (fallback فقط، يُستخدم إذا Qwen2-Audio
    غير متاح). نحوّل تصنيفات PANNs العامة لصياغة أقرب لأسلوب Suno عبر
    _PANNS_TO_PRODUCTION_STYLE بدل طباعة اسم الصنف الخام.
    """
    print("[4/5] تصنيف الآلات لكل مقطع (PANNs - fallback)...")
    from panns_inference import AudioTagging, labels
    import librosa
    import numpy as np

    ckpt_path = os.path.join(os.path.expanduser("~"), "panns_data", "Cnn14_mAP=0.431.pth")
    if not os.path.exists(ckpt_path):
        print("      تحميل PANNs checkpoint من HuggingFace (أسرع من Zenodo)...")
        from huggingface_hub import hf_hub_download

        os.makedirs(os.path.dirname(ckpt_path), exist_ok=True)
        downloaded = hf_hub_download(
            repo_id="thelou1s/panns-inference",
            filename="Cnn14_mAP=0.431.pth",
        )
        if not os.path.exists(ckpt_path):
            os.symlink(downloaded, ckpt_path)

    GENERIC_TAGS = {"music", "musical instrument", "speech", "sound effect", "singing"}

    at = AudioTagging(checkpoint_path=ckpt_path, device="cuda")
    y, sr = librosa.load(instrumental_path, sr=32000)

    tags_per_segment = {}
    for seg in segments:
        s_sample = int(seg["start"] * sr)
        e_sample = int(seg["end"] * sr)
        chunk = y[s_sample:e_sample]
        if len(chunk) < sr:
            continue
        clipwise_output, _ = at.inference(chunk[None, :])
        top_idx = np.argsort(clipwise_output[0])[-15:][::-1]
        top_tags = [
            labels[i] for i in top_idx
            if clipwise_output[0][i] > 0.08 and labels[i].lower() not in GENERIC_TAGS
        ][:4]
        styled = [
            _PANNS_TO_PRODUCTION_STYLE.get(t.lower(), t) for t in top_tags
        ]
        tags_per_segment[(seg["start"], seg["end"])] = styled
    return tags_per_segment


def describe_with_qwen_audio(instrumental_path: str, segments: list) -> dict:
    """
    وصف نصي حر للإنتاج الصوتي عبر Qwen2-Audio.

    تصحيح مهم: Qwen2-Audio لا يقبل تمرير prompt كنص عادي مع audios=chunk
    مباشرة — إذا ما فيه توكن `<|AUDIO|>` داخل النص، المعالج (processor)
    يتجاهل audios بالكامل بصمت (رسالة "audios is not a valid argument")
    والنموذج يولّد بدون أي إدخال صوتي فعلي (فيرجّع نفس الـ prompt أو
    يهلوس). الطريقة الصحيحة المعتمدة رسميًا: نبني النص عبر
    processor.apply_chat_template مع محادثة تحتوي على عنصر من نوع
    "audio"، وهذا يُدرج توكن الصوت بمكانه الصحيح تلقائيًا قبل تمرير
    audios= كمصفوفة numpy فعلية.
    """
    print("[اختياري/افتراضي] وصف الإنتاج الصوتي (Qwen2-Audio)...")
    from transformers import Qwen2AudioForConditionalGeneration, AutoProcessor
    import librosa

    model_id = "Qwen/Qwen2-Audio-7B-Instruct"
    processor = AutoProcessor.from_pretrained(model_id)
    model = Qwen2AudioForConditionalGeneration.from_pretrained(
        model_id, device_map="cuda", torch_dtype="auto"
    )
    target_sr = processor.feature_extractor.sampling_rate

    prompt_text = (
        "Describe this music segment with ONE very short production tag "
        "(3-6 words), in the style of Suno lyric-sheet annotations. "
        "Examples of the exact style wanted: "
        "distorted electric guitar power chords enter -- "
        "clean electric guitar arpeggio -- orchestral strings swell. "
        "Output ONLY the tag as plain text. Do not use quotes, brackets, "
        "or a full sentence."
    )

    # نحمّل الملف الآلي كامل مرة وحدة بمعدل العينات اللي يتوقعه المعالج
    y_full, _ = librosa.load(instrumental_path, sr=target_sr)

    descriptions = {}
    for seg in segments:
        s = int(seg["start"] * target_sr)
        e = int(seg["end"] * target_sr)
        chunk = y_full[s:e]
        if len(chunk) < target_sr:  # مقطع أقصر من ثانية -> تجاهل
            continue

        conversation = [
            {
                "role": "user",
                "content": [
                    {"type": "audio", "audio_url": "placeholder"},
                    {"type": "text", "text": prompt_text},
                ],
            }
        ]
        chat_text = processor.apply_chat_template(
            conversation, add_generation_prompt=True, tokenize=False
        )
        # ملاحظة: بعض إصدارات transformers (v4.55+) غيّرت اسم البارامتر
        # من `audios` إلى `audio` (مفرد) في معالج Qwen2-Audio. نحاول
        # `audio` أولًا، ولو فشل (إصدار أقدم) نرجع لـ `audios`.
        try:
            inputs = processor(
                text=chat_text, audio=[chunk], sampling_rate=target_sr, return_tensors="pt"
            ).to("cuda")
        except TypeError:
            inputs = processor(
                text=chat_text, audios=[chunk], sampling_rate=target_sr, return_tensors="pt"
            ).to("cuda")

        # فحص أمان: لو ما فيه input_features بالمدخلات، يعني الصوت ما
        # انحقن فعليًا (تجاهل صامت من المعالج) والنموذج راح يهلوس بدون
        # سياق صوتي حقيقي. نطبع تحذير واضح بدل ما نكتشفها من نوعية
        # المخرجات لاحقًا فقط.
        if "input_features" not in inputs:
            print(
                f"      ⚠️ تحذير: الصوت لم يُحقن بمدخلات المقطع {seg['start']:.1f}-{seg['end']:.1f}s "
                "— النتيجة قد تكون هلوسة نصية بدون سياق صوتي حقيقي."
            )

        out = model.generate(**inputs, max_new_tokens=20)
        # نقص التوكنات المدخلة عشان نرجّع فقط النص المولَّد الجديد
        new_tokens = out[:, inputs["input_ids"].shape[1]:]
        text = processor.batch_decode(new_tokens, skip_special_tokens=True)[0].strip()
        # تنظيف احتياطي: بعض المخرجات تجي مغلّفة بأقواس/اقتباسات على
        # شكل تمثيل قائمة بايثون (['...']) لأن النموذج قلّد شكل الأمثلة
        # بدل الالتزام الحرفي بـ "بدون أقواس ولا اقتباسات".
        text = text.strip("[]'\" ").strip()
        descriptions[(seg["start"], seg["end"])] = text
    return descriptions


def _assign_lines_to_segments(segments: list, lyrics_lines: list) -> list:
    """
    يحدد لكل سطر أي مقطع (segment) ينتمي له.

    تحسين v3: التعيين الأساسي بالتوقيت (أي مقطع يحوي بداية السطر)، لكن
    لو سطرين متتاليين ينتميان لنفس البيت الشعري (`bait_id` متطابق —
    يعني شطر أول وشطر ثاني من نفس البيت بملف poem.py) ووقعا بمقطعين
    مختلفين، نُجبر الشطر الثاني يلحق نفس مقطع الشطر الأول. هذا يمنع
    انقسام بيت واحد بين Verse وChorus لمجرد إن حد زمني وقع بالصدفة
    بمنتصف البيت.

    يرجّع قائمة (segment, assigned_lines) بنفس ترتيب `segments`.
    """
    assigned_idx_per_line = []
    last_bait_id, last_assigned_idx = None, None

    for line in lyrics_lines:
        if not line["text"].strip():
            continue
        raw_idx = None
        for i, seg in enumerate(segments):
            if seg["start"] <= line["start"] < seg["end"]:
                raw_idx = i
                break
        if raw_idx is None:
            raw_idx = len(segments) - 1  # آخر مقطع كحل احتياطي

        bait_id = line.get("bait_id")
        if bait_id is not None and bait_id == last_bait_id and raw_idx != last_assigned_idx:
            assigned_idx = last_assigned_idx  # نفس مقطع الشطر السابق من نفس البيت
        else:
            assigned_idx = raw_idx

        assigned_idx_per_line.append((assigned_idx, line["text"]))
        last_bait_id, last_assigned_idx = bait_id, assigned_idx

    lines_per_segment = [[] for _ in segments]
    for idx, text in assigned_idx_per_line:
        lines_per_segment[idx].append(text)

    return [
        {**seg, "lines": lines_per_segment[i]}
        for i, seg in enumerate(segments)
        if lines_per_segment[i]
    ]


def build_suno_format(segments, lyrics_lines, instrument_tags, qwen_desc=None) -> str:
    """
    يدمج كل النتائج بفورمات نصي شبيه بمخرجات Suno.

    تحسين v2: إزالة تكرار الأسطر المتتالية المتطابقة داخل نفس المقطع
    (زي كورس تكرر ٣-٤ مرات ASR بنفس التوقيت التقريبي)، حتى لا يظهر نفس
    البيت أكثر من مرتين متتاليتين.

    تحسين v3: تعيين الأسطر للمقاطع الآن يمر عبر _assign_lines_to_segments
    اللي يراعي وحدة البيت الشعري (bait_id) بدل التوقيت الخام فقط.
    """
    print("[5/5] بناء المخرج النهائي...")

    prepared = _assign_lines_to_segments(segments, lyrics_lines)

    merged = []
    for seg in prepared:
        if merged and merged[-1]["label"] == seg["label"]:
            merged[-1]["end"] = seg["end"]
            merged[-1]["lines"].extend(seg["lines"])
        else:
            merged.append(dict(seg))

    def _dedupe_consecutive(lines: list, max_repeats: int = 2) -> list:
        out_lines, run_val, run_count = [], None, 0
        for ln in lines:
            if ln == run_val:
                run_count += 1
            else:
                run_val, run_count = ln, 1
            if run_count <= max_repeats:
                out_lines.append(ln)
        return out_lines

    out = []
    for seg in merged:
        out.append(f"[{seg['label'].capitalize()}]")

        key = (seg["start"], seg["end"])
        if qwen_desc and key in qwen_desc:
            out.append(f"[{qwen_desc[key]}]")
        else:
            tags = []
            for (s, e), t in instrument_tags.items():
                if s < seg["end"] and e > seg["start"] and t:
                    tags = t
                    break
            if tags:
                out.append(f"[{', '.join(tags)}]")

        out.extend(_dedupe_consecutive(seg["lines"]))
        out.append("")
    return "\n".join(out)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio", required=True, help="مسار الملف الصوتي")
    parser.add_argument("--lang", default="ar", help="لغة الكلمات (ar/en/...)")
    parser.add_argument(
        "--no-qwen", action="store_true",
        help="تعطيل Qwen2-Audio والاعتماد على PANNs + قاموس التحويل فقط (لو GPU ما يكفي)",
    )
    parser.add_argument(
        "--reference-poem", default=None,
        help="مسار ملف poem.py يحتوي على poem_list لتصحيح مخرجات ASR تلقائيًا",
    )
    parser.add_argument("--out", default="lyrics_output_v2.txt")
    args = parser.parse_args()

    stems = separate_vocals(args.audio)
    lyrics = transcribe(stems["vocals"], lang=args.lang)

    if args.reference_poem:
        print("[+] محاذاة النص مع المرجع الصحيح (poem.py)...")
        reference_lines = load_reference_poem(args.reference_poem)
        lyrics = align_lyrics_to_reference(lyrics, reference_lines)

    structure = analyze_structure(args.audio, lyrics)

    qwen_desc = None
    inst_tags = {}
    if not args.no_qwen:
        try:
            qwen_desc = describe_with_qwen_audio(stems["instrumental"], structure)
        except Exception as e:  # فشل تحميل النموذج (GPU غير كافٍ مثلًا) -> fallback
            print(f"      تعذّر استخدام Qwen2-Audio ({e}), الرجوع لـ PANNs...")
            inst_tags = tag_instruments(stems["instrumental"], structure)
    else:
        inst_tags = tag_instruments(stems["instrumental"], structure)

    result_text = build_suno_format(structure, lyrics, inst_tags, qwen_desc)

    with open(args.out, "w", encoding="utf-8") as f:
        f.write(result_text)

    print(f"\n✅ تم الحفظ في: {args.out}\n")
    print(result_text)


if __name__ == "__main__":
    main()
