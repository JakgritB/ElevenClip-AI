"use client";
import { useState } from "react";
import { HexColorPicker } from "react-colorful";
import { Minus, Sun, Mic, Zap, Keyboard, ArrowUpDown, Heart, MessageCircle, Share2, Music } from "lucide-react";
import type { StyleConfig } from "@/lib/api";

const FONTS = [
  "Noto Sans Thai", "Noto Sans SC", "Noto Sans", "Impact",
  "Montserrat", "Oswald", "Anton", "Bebas Neue",
];

const ANIMATIONS = [
  { id: "none",       Icon: Minus,       en: "None",       th: "ไม่มี",     zh: "无" },
  { id: "fade",       Icon: Sun,         en: "Fade",       th: "Fade",      zh: "淡入" },
  { id: "karaoke",    Icon: Mic,         en: "Karaoke",    th: "Karaoke",   zh: "卡拉OK" },
  { id: "pop",        Icon: Zap,         en: "Pop",        th: "Pop",       zh: "弹出" },
  { id: "typewriter", Icon: Keyboard,    en: "Typewriter", th: "Typewriter",zh: "打字机" },
  { id: "bounce",     Icon: ArrowUpDown, en: "Bounce",     th: "Bounce",    zh: "弹跳" },
];

const ALIGNMENTS = [
  { val: 7, label: "↖" }, { val: 8, label: "↑" }, { val: 9, label: "↗" },
  { val: 4, label: "←" }, { val: 5, label: "·" }, { val: 6, label: "→" },
  { val: 1, label: "↙" }, { val: 2, label: "↓" }, { val: 3, label: "↘" },
];

const SAMPLE_TEXTS: Record<string, string> = {
  thai:     "นี่คือตัวอย่างซับไตเติ้ล",
  english:  "This is a sample subtitle",
  chinese:  "这是字幕示例",
  japanese: "これはサンプル字幕です",
  korean:   "이것은 샘플 자막입니다",
  default:  "Sample subtitle preview",
};

const L = {
  en: {
    font: "Font", size: "Size", outline: "Outline", shadow: "Shadow",
    colors: "Colors", primary: "Text", secondary: "Karaoke", outlineC: "Border", shadowC: "Shadow",
    word: "Word", sentence: "Sentence",
    animation: "Animation", animPreview: "Animation preview", position: "Position", close: "Close",
  },
  th: {
    font: "ฟ้อนต์", size: "ขนาด", outline: "ขอบ", shadow: "เงา",
    colors: "สี", primary: "ข้อความ", secondary: "Karaoke", outlineC: "ขอบ", shadowC: "เงา",
    word: "คำ", sentence: "ประโยค",
    animation: "แอนิเมชัน", animPreview: "ตัวอย่างแอนิเมชัน", position: "ตำแหน่ง", close: "ปิด",
  },
  zh: {
    font: "字体", size: "大小", outline: "描边", shadow: "阴影",
    colors: "颜色", primary: "文字", secondary: "卡拉OK", outlineC: "描边", shadowC: "阴影",
    word: "逐字", sentence: "句子",
    animation: "动画", animPreview: "动画预览", position: "位置", close: "关闭",
  },
} as const;

type Lang = keyof typeof L;

interface Props {
  config: StyleConfig;
  onChange: (c: Partial<StyleConfig>) => void;
  subtitleLanguage: string;
  uiLang?: Lang;
}

/* ── TikTok phone preview ── */
function TikTokPreview({ config, subtitleLanguage }: { config: StyleConfig; subtitleLanguage: string }) {
  const text = SAMPLE_TEXTS[subtitleLanguage] ?? SAMPLE_TEXTS.default;
  const alignment = config.alignment ?? 2;
  const isBottom = alignment <= 3;
  const isTop = alignment >= 7;
  const isLeft = [1, 4, 7].includes(alignment);
  const isRight = [3, 6, 9].includes(alignment);

  const posStyle: React.CSSProperties = {
    position: "absolute", zIndex: 10, maxWidth: "76%",
    wordBreak: "break-word",
    textAlign: isLeft ? "left" : isRight ? "right" : "center",
  };
  if (isBottom) {
    posStyle.bottom = "18%";
    posStyle.left = isLeft ? "4%" : isRight ? undefined : "12%";
    posStyle.right = isRight ? "14%" : isLeft ? undefined : "12%";
  } else if (isTop) {
    posStyle.top = "12%";
    posStyle.left = isLeft ? "4%" : isRight ? undefined : "12%";
    posStyle.right = isRight ? "14%" : isLeft ? undefined : "12%";
  } else {
    posStyle.top = "50%"; posStyle.transform = "translateY(-50%)";
    posStyle.left = isLeft ? "4%" : isRight ? undefined : "12%";
    posStyle.right = isRight ? "14%" : isLeft ? undefined : "12%";
  }

  const s = 0.34;
  const fontSize = Math.max(10, (config.font_size ?? 52) * s);
  const outlineW = (config.outline_size ?? 2.5) * s;
  const textShadow = outlineW > 0
    ? `${outlineW}px ${outlineW}px 0 ${config.outline_color ?? "#000"},
       -${outlineW}px ${outlineW}px 0 ${config.outline_color ?? "#000"},
       ${outlineW}px -${outlineW}px 0 ${config.outline_color ?? "#000"},
       -${outlineW}px -${outlineW}px 0 ${config.outline_color ?? "#000"}`
    : "none";

  const textStyle: React.CSSProperties = {
    fontFamily: `"${config.font_family ?? "Noto Sans"}", sans-serif`,
    fontSize: `${fontSize}px`, fontWeight: config.bold ? "bold" : "normal",
    fontStyle: config.italic ? "italic" : "normal",
    textDecoration: config.underline ? "underline" : "none",
    color: config.primary_color ?? "#FFFFFF", textShadow, lineHeight: 1.25,
  };

  return (
    <div className="flex justify-center">
      <div className="relative rounded-3xl overflow-hidden shadow-2xl border-4 border-gray-700 bg-black" style={{ width: 180, height: 320 }}>
        <div className="absolute inset-0 bg-gradient-to-br from-slate-900 via-purple-950 to-slate-900" />
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute" style={{ top: "30%", left: 0, right: 0, height: 1, background: "rgba(255,255,255,0.04)" }} />
          <div className="absolute" style={{ top: "60%", left: 0, right: 0, height: 1, background: "rgba(255,255,255,0.04)" }} />
        </div>
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-14 h-4 bg-black rounded-b-xl z-20" />
        <div className="absolute right-2 z-10 flex flex-col items-center gap-3" style={{ bottom: "22%" }}>
          {[{ Icon: Heart, count: "12.4K" }, { Icon: MessageCircle, count: "892" }, { Icon: Share2, count: "Share" }].map(({ Icon, count }, i) => (
            <div key={i} className="flex flex-col items-center gap-0.5">
              <div className="w-8 h-8 rounded-full bg-white/20 backdrop-blur-sm flex items-center justify-center">
                <Icon size={13} className="text-white" fill="rgba(255,255,255,0.9)" />
              </div>
              <span className="text-white text-[7px] font-semibold drop-shadow">{count}</span>
            </div>
          ))}
          <div className="mt-1">
            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-violet-500 to-pink-500 flex items-center justify-center">
              <Music size={12} className="text-white" />
            </div>
          </div>
        </div>
        <div className="absolute left-2 right-12 z-10" style={{ bottom: "8%" }}>
          <div className="text-white text-[9px] font-bold drop-shadow-md">@elevnclip_ai</div>
          <div className="text-white/75 text-[7.5px] mt-0.5 leading-tight drop-shadow">#highlight #tiktok #ai #amd</div>
        </div>
        <div className="absolute bottom-0 left-0 right-0 h-1 bg-white/20 z-10">
          <div className="h-full bg-white/70 w-2/5" />
        </div>
        <div style={posStyle}><span style={textStyle}>{text}</span></div>
        <div className="absolute top-6 left-2 z-20">
          <span className="text-[7px] text-white/35 font-mono tracking-widest">PREVIEW</span>
        </div>
      </div>
    </div>
  );
}

/* ── Animation CSS keyframes ── */
const ANIM_CSS = `
  @keyframes elevn-fade { 0%,100%{opacity:0} 30%,70%{opacity:1} }
  @keyframes elevn-pop { 0%,100%{transform:scale(0.5);opacity:0} 40%{transform:scale(1.12)} 50%,80%{transform:scale(1);opacity:1} }
  @keyframes elevn-bounce { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-9px)} }
  @keyframes elevn-type { from{clip-path:inset(0 100% 0 0)} to{clip-path:inset(0 0% 0 0)} }
`;

function AnimPreview({ animation, config, text }: { animation: string; config: StyleConfig; text: string }) {
  const s = 0.38;
  const fontSize = Math.max(12, (config.font_size ?? 52) * s);
  const outlineW = (config.outline_size ?? 2.5) * s;
  const textShadow = outlineW > 0
    ? `${outlineW}px ${outlineW}px 0 ${config.outline_color ?? "#000"}, -${outlineW}px ${outlineW}px 0 ${config.outline_color ?? "#000"}, ${outlineW}px -${outlineW}px 0 ${config.outline_color ?? "#000"}, -${outlineW}px -${outlineW}px 0 ${config.outline_color ?? "#000"}`
    : "none";

  const animMap: Record<string, string> = {
    fade: "elevn-fade 2s ease-in-out infinite",
    pop: "elevn-pop 1.8s ease-in-out infinite",
    bounce: "elevn-bounce 1s ease-in-out infinite",
    typewriter: "elevn-type 2.5s steps(20) infinite",
  };

  const baseStyle: React.CSSProperties = {
    fontFamily: `"${config.font_family ?? "Noto Sans"}", sans-serif`,
    fontSize: `${fontSize}px`,
    fontWeight: config.bold ? "bold" : "normal",
    fontStyle: config.italic ? "italic" : "normal",
    color: config.primary_color ?? "#fff",
    textShadow,
    display: "inline-block",
    whiteSpace: "nowrap",
    animation: animMap[animation] ?? "none",
  };

  return (
    <>
      <style>{ANIM_CSS}</style>
      <div className="bg-black/50 border border-white/10 rounded-xl h-12 flex items-center justify-center overflow-hidden">
        {animation === "karaoke" ? (
          <span style={{
            ...baseStyle,
            background: `linear-gradient(to right, ${config.secondary_color ?? "#ffff00"} 45%, ${config.primary_color ?? "#fff"} 45%)`,
            WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent",
            animation: "none",
          }}>
            {text}
          </span>
        ) : (
          <span style={baseStyle}>{text}</span>
        )}
      </div>
    </>
  );
}

export default function SubtitleDesigner({ config, onChange, subtitleLanguage, uiLang = "en" }: Props) {
  const [colorPicker, setColorPicker] = useState<string | null>(null);
  const lbl = L[uiLang];
  const sampleText = SAMPLE_TEXTS[subtitleLanguage] ?? SAMPLE_TEXTS.default;

  const colorFields = [
    { key: "primary_color",   label: lbl.primary },
    { key: "secondary_color", label: lbl.secondary },
    { key: "outline_color",   label: lbl.outlineC },
    { key: "shadow_color",    label: lbl.shadowC },
  ];

  return (
    <div className="flex gap-3 items-start">

      {/* Col 1 — TikTok preview */}
      <div className="shrink-0">
        <TikTokPreview config={config} subtitleLanguage={subtitleLanguage} />
      </div>

      {/* Col 2 — Typography controls */}
      <div className="w-[170px] shrink-0 space-y-2">
        {/* Font */}
        <div className="space-y-1">
          <label className="text-xs font-medium text-white/60">{lbl.font}</label>
          <select
            value={config.font_family ?? "Noto Sans"}
            onChange={(e) => onChange({ font_family: e.target.value })}
            className="w-full bg-white/5 border border-white/20 rounded-lg px-2 py-1.5 text-xs text-white focus:outline-none focus:border-violet-500"
          >
            {FONTS.map((f) => <option key={f} value={f} className="bg-gray-900">{f}</option>)}
          </select>
        </div>
        {/* Size */}
        <div className="space-y-1">
          <label className="text-xs font-medium text-white/60">{lbl.size} ({config.font_size ?? 52}px)</label>
          <input type="range" min={20} max={96} step={2}
            value={config.font_size ?? 52}
            onChange={(e) => onChange({ font_size: +e.target.value })}
            className="w-full mt-1 accent-violet-500" />
        </div>
        {/* Outline */}
        <div className="space-y-1">
          <label className="text-xs font-medium text-white/60">{lbl.outline} ({config.outline_size ?? 2.5}px)</label>
          <input type="range" min={0} max={10} step={0.5}
            value={config.outline_size ?? 2.5}
            onChange={(e) => onChange({ outline_size: +e.target.value })}
            className="w-full mt-1 accent-violet-500" />
        </div>
        {/* Shadow */}
        <div className="space-y-1">
          <label className="text-xs font-medium text-white/60">{lbl.shadow} ({config.shadow_size ?? 1.5}px)</label>
          <input type="range" min={0} max={10} step={0.5}
            value={config.shadow_size ?? 1.5}
            onChange={(e) => onChange({ shadow_size: +e.target.value })}
            className="w-full mt-1 accent-violet-500" />
        </div>
        {/* B/I/U */}
        <div className="flex items-center gap-1.5 flex-wrap">
          {[
            { key: "bold",      label: "B", cls: "font-bold" },
            { key: "italic",    label: "I", cls: "italic" },
            { key: "underline", label: "U", cls: "underline" },
          ].map(({ key, label, cls }) => (
            <button key={key}
              onClick={() => onChange({ [key]: !(config as Record<string, unknown>)[key] })}
              className={`w-8 h-8 rounded-lg border text-sm transition ${cls} ${
                (config as Record<string, unknown>)[key]
                  ? "border-violet-500 bg-violet-600 text-white"
                  : "border-white/20 bg-white/5 text-white/50 hover:text-white"
              }`}>
              {label}
            </button>
          ))}
        </div>
        {/* Display mode */}
        <div className="flex gap-1.5">
          {[{ id: "word", label: lbl.word }, { id: "sentence", label: lbl.sentence }].map((m) => (
            <button key={m.id}
              onClick={() => onChange({ display_mode: m.id as "word" | "sentence" })}
              className={`flex-1 py-1.5 rounded-lg text-xs font-medium transition ${
                config.display_mode === m.id
                  ? "bg-violet-600 text-white"
                  : "bg-white/5 text-white/50 border border-white/10 hover:text-white"
              }`}>
              {m.label}
            </button>
          ))}
        </div>
      </div>

      {/* Col 3 — Colors, Animation, Position */}
      <div className="flex-1 min-w-0 space-y-2">
        {/* Colors */}
        <div className="space-y-1">
          <label className="text-xs font-medium text-white/60">{lbl.colors}</label>
          <div className="grid grid-cols-4 gap-1.5">
            {colorFields.map(({ key, label }) => (
              <div key={key} className="relative">
                <button
                  onClick={() => setColorPicker(colorPicker === key ? null : key)}
                  className="w-full flex flex-col items-center gap-1 p-1.5 rounded-xl border border-white/10 hover:border-violet-400 transition bg-white/5">
                  <span className="w-7 h-7 rounded-lg border border-white/20 block"
                    style={{ background: (config as Record<string, string>)[key] ?? "#ffffff" }} />
                  <span className="text-[9px] text-white/50 text-center leading-none">{label}</span>
                </button>
                {colorPicker === key && (
                  <div className="absolute z-50 top-full mt-1 left-0">
                    <div className="p-2 bg-gray-900 border border-white/20 rounded-xl shadow-2xl">
                      <HexColorPicker
                        color={(config as Record<string, string>)[key] ?? "#ffffff"}
                        onChange={(c) => onChange({ [key]: c })} />
                      <button onClick={() => setColorPicker(null)}
                        className="mt-2 w-full text-xs text-white/40 hover:text-white">
                        {lbl.close}
                      </button>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Animation preview + picker combined */}
        <div className="space-y-1.5">
          <label className="text-xs font-medium text-white/60">{lbl.animation}</label>
          <AnimPreview animation={config.animation ?? "none"} config={config} text={sampleText} />
          <div className="grid grid-cols-3 gap-1.5 mt-1.5">
            {ANIMATIONS.map(({ id, Icon, en, th, zh }) => {
              const animLabel = uiLang === "th" ? th : uiLang === "zh" ? zh : en;
              return (
                <button key={id}
                  onClick={() => onChange({ animation: id as StyleConfig["animation"] })}
                  className={`py-1.5 px-1.5 rounded-xl text-xs font-medium transition flex items-center justify-center gap-1 ${
                    config.animation === id
                      ? "bg-violet-600 text-white ring-2 ring-violet-400"
                      : "bg-white/5 text-white/50 border border-white/10 hover:text-white hover:bg-white/10"
                  }`}>
                  <Icon size={11} /> {animLabel}
                </button>
              );
            })}
          </div>
        </div>

        {/* Position */}
        <div className="space-y-1">
          <label className="text-xs font-medium text-white/60">{lbl.position}</label>
          <div className="flex items-start gap-3">
            <div className="grid grid-cols-3 gap-0.5 w-20 shrink-0">
              {ALIGNMENTS.map((a) => (
                <button key={a.val}
                  onClick={() => onChange({ alignment: a.val })}
                  className={`aspect-square rounded text-xs font-bold transition ${
                    config.alignment === a.val
                      ? "bg-violet-600 text-white"
                      : "bg-white/10 text-white/50 hover:bg-white/20"
                  }`}>
                  {a.label}
                </button>
              ))}
            </div>
            <div className="flex-1 space-y-1 pt-1">
              <label className="text-xs text-white/50">Margin ({config.margin_v ?? 250}px)</label>
              <input type="range" min={50} max={800} step={10}
                value={config.margin_v ?? 250}
                onChange={(e) => onChange({ margin_v: +e.target.value })}
                className="w-full accent-violet-500" />
            </div>
          </div>
        </div>
      </div>

    </div>
  );
}
