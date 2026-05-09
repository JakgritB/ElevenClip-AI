"use client";
import { Laugh, Target, BookOpen, Gamepad2, Tv, Zap, Bot, Film } from "lucide-react";

const STYLES = [
  { id: "funny",         Icon: Laugh,    en: "Funny",         th: "ตลก",       zh: "搞笑" },
  { id: "serious",       Icon: Target,   en: "Serious",       th: "จริงจัง",   zh: "严肃" },
  { id: "educational",   Icon: BookOpen, en: "Educational",   th: "ให้ความรู้", zh: "教育" },
  { id: "gaming",        Icon: Gamepad2, en: "Gaming",        th: "เกมมิ่ง",   zh: "游戏" },
  { id: "entertainment", Icon: Tv,       en: "Entertainment", th: "บันเทิง",   zh: "娱乐" },
];

const DURATIONS = [15, 30, 45, 60, 90];

const LANGUAGES = [
  { code: "auto",       label: "Auto-detect" },
  { code: "thai",       label: "ภาษาไทย" },
  { code: "english",    label: "English" },
  { code: "chinese",    label: "中文 (简体)" },
  { code: "japanese",   label: "日本語" },
  { code: "korean",     label: "한국어" },
  { code: "french",     label: "Français" },
  { code: "german",     label: "Deutsch" },
  { code: "spanish",    label: "Español" },
  { code: "portuguese", label: "Português" },
  { code: "russian",    label: "Русский" },
  { code: "arabic",     label: "العربية" },
  { code: "hindi",      label: "हिंदी" },
  { code: "vietnamese", label: "Tiếng Việt" },
  { code: "indonesian", label: "Bahasa Indonesia" },
];

const L = {
  en: {
    style: "Clip Style",
    duration: "Duration (seconds)",
    count: "Clip Count",
    videoLang: "Video Language",
    subLang: "Subtitle Language",
    mode: "Editing Mode",
    normalTitle: "Normal Subtitles",
    normalDesc: "Customize font, colors, animations",
    hreTitle: "High-Retention",
    hreDesc: "AI picks timing, captions, and zoom",
    hreInfo: "AI will create a per-segment edit plan, vary caption placement/mode, zoom on key moments, and add emoji overlays.",
  },
  th: {
    style: "สไตล์คลิป",
    duration: "ความยาว (วินาที)",
    count: "จำนวนคลิป",
    videoLang: "ภาษาของวิดีโอ",
    subLang: "ภาษาของซับ",
    mode: "โหมดการตัด",
    normalTitle: "ซับปกติ",
    normalDesc: "เลือกรูปแบบซับได้เอง",
    hreTitle: "High-Retention",
    hreDesc: "AI เลือกจังหวะ ซับ และซูมให้",
    hreInfo: "AI จะสร้างแผนตัดต่อรายช่วง เลือกตำแหน่ง/รูปแบบซับ ซูมช่วงสำคัญ และใส่ emoji ให้อัตโนมัติ",
  },
  zh: {
    style: "片段风格",
    duration: "时长（秒）",
    count: "片段数量",
    videoLang: "视频语言",
    subLang: "字幕语言",
    mode: "剪辑模式",
    normalTitle: "普通字幕",
    normalDesc: "自定义字体、颜色、动画",
    hreTitle: "高留存",
    hreDesc: "AI 自动选择节奏、字幕和缩放",
    hreInfo: "AI 将生成分段剪辑计划，调整字幕位置/模式，缩放关键时刻，并添加表情覆盖。",
  },
} as const;

type Lang = keyof typeof L;

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
  uiLang?: Lang;
}

export default function ClipSettings({ settings, onChange, uiLang = "en" }: Props) {
  const lbl = L[uiLang];

  return (
    <div className="space-y-2.5">
      {/* Style — horizontal buttons (icon + label in one line) */}
      <div className="space-y-1.5">
        <label className="text-xs font-medium text-white/60">{lbl.style}</label>
        <div className="grid grid-cols-5 gap-1.5">
          {STYLES.map(({ id, Icon, en, th, zh }) => {
            const label = uiLang === "th" ? th : uiLang === "zh" ? zh : en;
            return (
              <button
                key={id}
                onClick={() => onChange({ clip_style: id })}
                className={`py-1.5 px-1 rounded-xl text-xs font-medium transition text-center flex items-center justify-center gap-1 ${
                  settings.clip_style === id
                    ? "bg-violet-600 text-white ring-2 ring-violet-400"
                    : "bg-white/5 text-white/60 hover:bg-white/10 hover:text-white border border-white/10"
                }`}
              >
                <Icon size={12} />
                <span className="truncate">{label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Duration + Count */}
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <label className="text-xs font-medium text-white/60">{lbl.duration}</label>
          <div className="flex gap-1">
            {DURATIONS.map((d) => (
              <button
                key={d}
                onClick={() => onChange({ target_duration: d })}
                className={`flex-1 py-1.5 rounded-lg text-xs font-medium transition ${
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

        <div className="space-y-1.5">
          <label className="text-xs font-medium text-white/60">{lbl.count}</label>
          <div className="flex items-center gap-2">
            <button
              onClick={() => onChange({ clip_count: Math.max(1, settings.clip_count - 1) })}
              className="w-8 h-8 rounded-lg bg-white/10 hover:bg-white/20 text-white font-bold transition"
            >
              −
            </button>
            <span className="text-xl font-bold text-white w-6 text-center">{settings.clip_count}</span>
            <button
              onClick={() => onChange({ clip_count: Math.min(10, settings.clip_count + 1) })}
              className="w-8 h-8 rounded-lg bg-white/10 hover:bg-white/20 text-white font-bold transition"
            >
              +
            </button>
          </div>
        </div>
      </div>

      {/* Languages */}
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <label className="text-xs font-medium text-white/60">{lbl.videoLang}</label>
          <select
            value={settings.clip_language}
            onChange={(e) => onChange({ clip_language: e.target.value })}
            className="w-full bg-white/5 border border-white/20 rounded-xl px-3 py-1.5 text-sm text-white focus:outline-none focus:border-violet-500 transition"
          >
            {LANGUAGES.map((l) => (
              <option key={l.code} value={l.code} className="bg-gray-900">{l.label}</option>
            ))}
          </select>
        </div>

        <div className="space-y-1.5">
          <label className="text-xs font-medium text-white/60">{lbl.subLang}</label>
          <select
            value={settings.subtitle_language}
            onChange={(e) => onChange({ subtitle_language: e.target.value })}
            className="w-full bg-white/5 border border-white/20 rounded-xl px-3 py-1.5 text-sm text-white focus:outline-none focus:border-violet-500 transition"
          >
            {LANGUAGES.filter((l) => l.code !== "auto").map((l) => (
              <option key={l.code} value={l.code} className="bg-gray-900">{l.label}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Mode */}
      <div className="space-y-2">
        <label className="text-xs font-medium text-white/60">{lbl.mode}</label>
        <div className="grid grid-cols-2 gap-2">
          <button
            onClick={() => onChange({ mode: "normal" })}
            className={`p-2.5 rounded-xl border text-left transition-all ${
              settings.mode === "normal"
                ? "border-violet-500 bg-violet-600/20 text-white"
                : "border-white/10 bg-white/5 text-white/60 hover:border-white/30"
            }`}
          >
            <div className="font-medium text-xs mb-0.5 flex items-center gap-1.5"><Film size={12} /> {lbl.normalTitle}</div>
            <div className="text-[11px] opacity-70">{lbl.normalDesc}</div>
          </button>

          <button
            onClick={() => onChange({ mode: "hre" })}
            className={`p-2.5 rounded-xl border text-left transition-all ${
              settings.mode === "hre"
                ? "border-orange-500 bg-orange-600/20 text-white"
                : "border-white/10 bg-white/5 text-white/60 hover:border-white/30"
            }`}
          >
            <div className="font-medium text-xs mb-0.5 flex items-center gap-1.5"><Zap size={12} /> {lbl.hreTitle}</div>
            <div className="text-[11px] opacity-70">{lbl.hreDesc}</div>
          </button>
        </div>

        {settings.mode === "hre" && (
          <div className="bg-orange-500/10 border border-orange-500/30 rounded-xl p-2 text-xs text-orange-200 flex items-start gap-2">
            <Bot size={12} className="shrink-0 mt-0.5" />
            <span>{lbl.hreInfo}</span>
          </div>
        )}
      </div>
    </div>
  );
}
