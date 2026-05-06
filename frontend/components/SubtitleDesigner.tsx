"use client";
import { useState, useRef, useEffect } from "react";
import { HexColorPicker } from "react-colorful";
import type { StyleConfig } from "@/lib/api";

const FONTS = [
  "Noto Sans Thai", "Noto Sans SC", "Noto Sans", "Impact",
  "Montserrat", "Oswald", "Anton", "Bebas Neue",
];

const ANIMATIONS = [
  { id: "none", label: "ไม่มี" },
  { id: "fade", label: "Fade" },
  { id: "karaoke", label: "คาราโอเกะ 🎤" },
  { id: "pop", label: "Pop 💥" },
  { id: "typewriter", label: "Typewriter ⌨️" },
  { id: "bounce", label: "Bounce 🏀" },
];

// 3x3 alignment grid (ASS numpad alignment)
const ALIGNMENTS = [
  { val: 7, label: "↖" }, { val: 8, label: "↑" }, { val: 9, label: "↗" },
  { val: 4, label: "←" }, { val: 5, label: "·" }, { val: 6, label: "→" },
  { val: 1, label: "↙" }, { val: 2, label: "↓" }, { val: 3, label: "↘" },
];

const SAMPLE_TEXTS: Record<string, string> = {
  thai: "นี่คือตัวอย่างซับไตเติ้ล",
  english: "This is a sample subtitle",
  chinese: "这是字幕示例",
  japanese: "これはサンプル字幕です",
  korean: "이것은 샘플 자막입니다",
  default: "Sample subtitle preview",
};

interface Props {
  config: StyleConfig;
  onChange: (c: Partial<StyleConfig>) => void;
  subtitleLanguage: string;
}

export default function SubtitleDesigner({ config, onChange, subtitleLanguage }: Props) {
  const [colorPicker, setColorPicker] = useState<string | null>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  // Render preview on canvas whenever config changes
  useEffect(() => {
    renderPreview();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [config, subtitleLanguage]);

  const renderPreview = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const W = canvas.width;
    const H = canvas.height;

    // Background
    ctx.fillStyle = "#1a1a2e";
    ctx.fillRect(0, 0, W, H);

    // Simulated video content
    ctx.fillStyle = "#16213e";
    ctx.fillRect(20, 20, W - 40, H - 80);

    const text = SAMPLE_TEXTS[subtitleLanguage] ?? SAMPLE_TEXTS.default;
    const fontSize = Math.min(config.font_size ?? 52, 48);
    const fontFamily = config.font_family ?? "Noto Sans";

    ctx.font = `${config.bold ? "bold" : "normal"} ${fontSize}px "${fontFamily}", sans-serif`;

    // Alignment → x,y position
    const alignment = config.alignment ?? 2;
    const marginH = config.margin_l ?? 20;
    const marginV = config.margin_v ?? 40;
    const row = Math.floor((9 - alignment) / 3);
    const col = (alignment - 1) % 3;

    let x = W / 2;
    let y = H - marginV - fontSize;

    if (col === 0) x = marginH + fontSize;
    if (col === 2) x = W - marginH - fontSize;
    if (row === 0) y = H - marginV - fontSize;
    if (row === 1) y = H / 2;
    if (row === 2) y = marginV + fontSize;

    ctx.textAlign = col === 0 ? "left" : col === 2 ? "right" : "center";
    ctx.textBaseline = "bottom";

    // Outline
    const outlineSize = config.outline_size ?? 2.5;
    if (outlineSize > 0) {
      ctx.strokeStyle = config.outline_color ?? "#000000";
      ctx.lineWidth = outlineSize * 2;
      ctx.strokeText(text, x, y);
    }

    // Primary text
    ctx.fillStyle = config.primary_color ?? "#FFFFFF";
    ctx.fillText(text, x, y);

    // Preview label
    ctx.font = "11px sans-serif";
    ctx.fillStyle = "rgba(255,255,255,0.4)";
    ctx.textAlign = "left";
    ctx.fillText("PREVIEW", 8, 14);
  };

  const colorFields: Array<{ key: keyof StyleConfig; label: string }> = [
    { key: "primary_color", label: "สีตัวอักษรหลัก" },
    { key: "secondary_color", label: "สีก่อน Karaoke" },
    { key: "outline_color", label: "สีขอบ" },
    { key: "shadow_color", label: "สีเงา" },
  ];

  return (
    <div className="space-y-5">
      {/* Canvas preview */}
      <div className="relative">
        <canvas
          ref={canvasRef}
          width={500}
          height={120}
          className="w-full rounded-xl border border-white/10"
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        {/* Font */}
        <div className="space-y-2">
          <label className="text-xs font-medium text-white/60">ฟ้อนต์</label>
          <select
            value={config.font_family ?? "Noto Sans"}
            onChange={(e) => onChange({ font_family: e.target.value })}
            className="w-full bg-white/5 border border-white/20 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-violet-500"
          >
            {FONTS.map((f) => <option key={f} value={f} className="bg-gray-900">{f}</option>)}
          </select>
        </div>

        {/* Font size */}
        <div className="space-y-2">
          <label className="text-xs font-medium text-white/60">ขนาด ({config.font_size ?? 52}px)</label>
          <input
            type="range" min={20} max={96} step={2}
            value={config.font_size ?? 52}
            onChange={(e) => onChange({ font_size: +e.target.value })}
            className="w-full accent-violet-500"
          />
        </div>

        {/* Outline size */}
        <div className="space-y-2">
          <label className="text-xs font-medium text-white/60">ขนาดขอบ ({config.outline_size ?? 2.5}px)</label>
          <input
            type="range" min={0} max={10} step={0.5}
            value={config.outline_size ?? 2.5}
            onChange={(e) => onChange({ outline_size: +e.target.value })}
            className="w-full accent-violet-500"
          />
        </div>

        {/* Shadow size */}
        <div className="space-y-2">
          <label className="text-xs font-medium text-white/60">ขนาดเงา ({config.shadow_size ?? 1.5}px)</label>
          <input
            type="range" min={0} max={10} step={0.5}
            value={config.shadow_size ?? 1.5}
            onChange={(e) => onChange({ shadow_size: +e.target.value })}
            className="w-full accent-violet-500"
          />
        </div>
      </div>

      {/* Bold / Italic / Underline */}
      <div className="flex gap-2">
        {[
          { key: "bold", label: "B", style: "font-bold" },
          { key: "italic", label: "I", style: "italic" },
          { key: "underline", label: "U", style: "underline" },
        ].map(({ key, label, style }) => (
          <button
            key={key}
            onClick={() => onChange({ [key]: !(config as Record<string, unknown>)[key] })}
            className={`w-10 h-10 rounded-lg border text-sm transition-all ${style} ${
              (config as Record<string, unknown>)[key]
                ? "border-violet-500 bg-violet-600 text-white"
                : "border-white/20 bg-white/5 text-white/50 hover:text-white"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Colors */}
      <div className="grid grid-cols-2 gap-3">
        {colorFields.map(({ key, label }) => (
          <div key={key} className="space-y-1 relative">
            <label className="text-xs font-medium text-white/60">{label}</label>
            <button
              onClick={() => setColorPicker(colorPicker === key ? null : key)}
              className="w-full h-10 rounded-lg border border-white/20 flex items-center gap-2 px-3 transition hover:border-violet-400"
            >
              <span
                className="w-6 h-6 rounded-md border border-white/20"
                style={{ background: (config as Record<string, unknown>)[key] as string ?? "#ffffff" }}
              />
              <span className="text-sm text-white/70 font-mono">
                {(config as Record<string, unknown>)[key] as string ?? "#ffffff"}
              </span>
            </button>
            {colorPicker === key && (
              <div className="absolute z-50 top-full mt-2 left-0">
                <div className="p-2 bg-gray-900 border border-white/20 rounded-xl shadow-2xl">
                  <HexColorPicker
                    color={(config as Record<string, unknown>)[key] as string ?? "#ffffff"}
                    onChange={(c) => onChange({ [key]: c })}
                  />
                  <button
                    onClick={() => setColorPicker(null)}
                    className="mt-2 w-full text-xs text-white/50 hover:text-white"
                  >
                    ปิด
                  </button>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Display mode */}
      <div className="space-y-2">
        <label className="text-xs font-medium text-white/60">รูปแบบการแสดงผล</label>
        <div className="flex gap-2">
          {[{ id: "word", label: "คำต่อคำ" }, { id: "sentence", label: "ประโยค" }].map((m) => (
            <button
              key={m.id}
              onClick={() => onChange({ display_mode: m.id as "word" | "sentence" })}
              className={`flex-1 py-2 rounded-lg text-sm font-medium transition ${
                config.display_mode === m.id
                  ? "bg-violet-600 text-white"
                  : "bg-white/5 text-white/50 border border-white/10 hover:text-white"
              }`}
            >
              {m.label}
            </button>
          ))}
        </div>
      </div>

      {/* Animation */}
      <div className="space-y-2">
        <label className="text-xs font-medium text-white/60">แอนิเมชัน</label>
        <div className="grid grid-cols-3 gap-2">
          {ANIMATIONS.map((a) => (
            <button
              key={a.id}
              onClick={() => onChange({ animation: a.id as StyleConfig["animation"] })}
              className={`py-2 rounded-lg text-xs font-medium transition ${
                config.animation === a.id
                  ? "bg-violet-600 text-white"
                  : "bg-white/5 text-white/50 border border-white/10 hover:text-white"
              }`}
            >
              {a.label}
            </button>
          ))}
        </div>
      </div>

      {/* Alignment */}
      <div className="space-y-2">
        <label className="text-xs font-medium text-white/60">ตำแหน่ง</label>
        <div className="grid grid-cols-3 gap-1 w-28">
          {ALIGNMENTS.map((a) => (
            <button
              key={a.val}
              onClick={() => onChange({ alignment: a.val })}
              className={`aspect-square rounded-lg text-sm font-bold transition ${
                config.alignment === a.val
                  ? "bg-violet-600 text-white"
                  : "bg-white/10 text-white/50 hover:bg-white/20"
              }`}
            >
              {a.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
