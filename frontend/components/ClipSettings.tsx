"use client";

const STYLES = [
  { id: "funny", label: "ตลก 😂", en: "Funny" },
  { id: "serious", label: "จริงจัง 🎯", en: "Serious" },
  { id: "educational", label: "ให้ความรู้ 📚", en: "Educational" },
  { id: "gaming", label: "เกมมิ่ง 🎮", en: "Gaming" },
  { id: "entertainment", label: "บันเทิง 🎭", en: "Entertainment" },
];

const DURATIONS = [15, 30, 45, 60, 90];

const LANGUAGES = [
  { code: "auto", label: "Auto-detect" },
  { code: "thai", label: "ภาษาไทย" },
  { code: "english", label: "English" },
  { code: "chinese", label: "中文 (简体)" },
  { code: "japanese", label: "日本語" },
  { code: "korean", label: "한국어" },
  { code: "french", label: "Français" },
  { code: "german", label: "Deutsch" },
  { code: "spanish", label: "Español" },
  { code: "portuguese", label: "Português" },
  { code: "russian", label: "Русский" },
  { code: "arabic", label: "العربية" },
  { code: "hindi", label: "हिंदी" },
  { code: "vietnamese", label: "Tiếng Việt" },
  { code: "indonesian", label: "Bahasa Indonesia" },
];

interface Settings {
  clip_style: string;
  target_duration: number;
  clip_count: number;
  clip_language: string;
  subtitle_language: string;
  mode: "normal" | "hre";
}

interface Props {
  settings: Settings;
  onChange: (s: Partial<Settings>) => void;
}

export default function ClipSettings({ settings, onChange }: Props) {
  return (
    <div className="space-y-6">
      {/* Style */}
      <div className="space-y-2">
        <label className="text-sm font-medium text-white/70">สไตล์คลิป</label>
        <div className="grid grid-cols-5 gap-2">
          {STYLES.map((s) => (
            <button
              key={s.id}
              onClick={() => onChange({ clip_style: s.id })}
              className={`py-3 px-2 rounded-xl text-sm font-medium transition-all text-center ${
                settings.clip_style === s.id
                  ? "bg-violet-600 text-white ring-2 ring-violet-400"
                  : "bg-white/5 text-white/60 hover:bg-white/10 hover:text-white border border-white/10"
              }`}
            >
              {s.label}
            </button>
          ))}
        </div>
      </div>

      {/* Duration + Count */}
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <label className="text-sm font-medium text-white/70">ความยาว (วินาที)</label>
          <div className="flex gap-2 flex-wrap">
            {DURATIONS.map((d) => (
              <button
                key={d}
                onClick={() => onChange({ target_duration: d })}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                  settings.target_duration === d
                    ? "bg-violet-600 text-white"
                    : "bg-white/5 text-white/60 hover:bg-white/10 border border-white/10"
                }`}
              >
                {d}s
              </button>
            ))}
          </div>
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium text-white/70">จำนวนคลิป</label>
          <div className="flex items-center gap-3">
            <button
              onClick={() => onChange({ clip_count: Math.max(1, settings.clip_count - 1) })}
              className="w-10 h-10 rounded-lg bg-white/10 hover:bg-white/20 text-white font-bold transition"
            >
              −
            </button>
            <span className="text-2xl font-bold text-white w-8 text-center">{settings.clip_count}</span>
            <button
              onClick={() => onChange({ clip_count: Math.min(10, settings.clip_count + 1) })}
              className="w-10 h-10 rounded-lg bg-white/10 hover:bg-white/20 text-white font-bold transition"
            >
              +
            </button>
          </div>
        </div>
      </div>

      {/* Languages */}
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <label className="text-sm font-medium text-white/70">ภาษาของวิดีโอ</label>
          <select
            value={settings.clip_language}
            onChange={(e) => onChange({ clip_language: e.target.value })}
            className="w-full bg-white/5 border border-white/20 rounded-xl px-3 py-3 text-white focus:outline-none focus:border-violet-500 transition"
          >
            {LANGUAGES.map((l) => (
              <option key={l.code} value={l.code} className="bg-gray-900">
                {l.label}
              </option>
            ))}
          </select>
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium text-white/70">ภาษาของซับ</label>
          <select
            value={settings.subtitle_language}
            onChange={(e) => onChange({ subtitle_language: e.target.value })}
            className="w-full bg-white/5 border border-white/20 rounded-xl px-3 py-3 text-white focus:outline-none focus:border-violet-500 transition"
          >
            {LANGUAGES.filter((l) => l.code !== "auto").map((l) => (
              <option key={l.code} value={l.code} className="bg-gray-900">
                {l.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Mode */}
      <div className="space-y-3">
        <label className="text-sm font-medium text-white/70">โหมดการตัด</label>
        <div className="grid grid-cols-2 gap-3">
          <button
            onClick={() => onChange({ mode: "normal" })}
            className={`p-4 rounded-xl border text-left transition-all ${
              settings.mode === "normal"
                ? "border-violet-500 bg-violet-600/20 text-white"
                : "border-white/10 bg-white/5 text-white/60 hover:border-white/30"
            }`}
          >
            <div className="font-medium mb-1">🎬 ซับปกติ</div>
            <div className="text-xs opacity-70">เลือกรูปแบบซับได้เอง</div>
          </button>

          <button
            onClick={() => onChange({ mode: "hre" })}
            className={`p-4 rounded-xl border text-left transition-all ${
              settings.mode === "hre"
                ? "border-orange-500 bg-orange-600/20 text-white"
                : "border-white/10 bg-white/5 text-white/60 hover:border-white/30"
            }`}
          >
            <div className="font-medium mb-1">⚡ High-Retention</div>
            <div className="text-xs opacity-70">AI เลือกทุกอย่างให้ + auto-zoom + jump cuts</div>
          </button>
        </div>
        {settings.mode === "hre" && (
          <div className="bg-orange-500/10 border border-orange-500/30 rounded-xl p-3 text-sm text-orange-200">
            🤖 AI จะเลือก font/สี/animation + ตัด silence + zoom หน้าคน + ใส่ emoji ให้อัตโนมัติ ไม่ต้องตั้งค่าอะไรเพิ่ม
          </div>
        )}
      </div>
    </div>
  );
}
