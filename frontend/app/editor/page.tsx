"use client";
import { useEffect, useState, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { HexColorPicker } from "react-colorful";
import { getClips, patchSubtitle, patchGlobalStyle, renderClip, type ClipResult, type StyleConfig, type SubtitleEvent } from "@/lib/api";
import {
  Download, RotateCcw, ChevronLeft, Loader2, Bot, Scissors, CheckCircle2,
  Copy, Check, FileText, Palette, Scissors as ScissorsIcon, Plus, X,
  Heart, MessageCircle, Share2, Music,
} from "lucide-react";

const DEMO_CLIP_URLS = [
  "/demo/elevenclip_demo_01.mp4",
  "/demo/elevenclip_demo_02.mp4",
  "/demo/elevenclip_demo_03.mp4",
];

// ─── Types ────────────────────────────────────────────────────────────────────
type SubEvent = SubtitleEvent;
type SubLineStyle = {
  font_family?: string; font_size?: number;
  primary_color?: string; secondary_color?: string;
  outline_color?: string; shadow_color?: string;
  outline_size?: number; shadow_size?: number;
  bold?: boolean; italic?: boolean; animation?: string;
  alignment?: number; margin_v?: number;
};
type CutRegion = { id: number; from: number; to: number };
type Lang = "en" | "th" | "zh";

// ─── Translations ─────────────────────────────────────────────────────────────
const L = {
  en: {
    back: "Back", clips: "CLIPS", clip: "Clip",
    duration: "Duration", aiScore: "AI Score",
    render: "Render", download: "Download", rendering: "Rendering…", reRender: "Re-render",
    whyPicked: "Why AI picked this clip",
    caption: "Suggested caption", copy: "Copy", copied: "Copied",
    trimTab: "Trim & Cut", subsTab: "Subtitles",
    adjustBounds: "Adjust boundaries (±10s)", startOff: "Start offset", endOff: "End offset",
    cutMiddle: "Cut from middle", addCut: "+ Add cut",
    noCuts: "No cuts yet — click \"Add cut\" to remove a section from the middle",
    totalRemoved: "Total removed", finalDuration: "Final duration",
    subStyle: "Subtitle Style",
    global: "🌐 Global", perLine: "✨ Per-line",
    styleBtn: "Style ▾", styledBtn: "Styled ▾",
    font: "Font", size: "Size", outline: "Outline", shadow: "Shadow",
    colorText: "Text", colorKaraoke: "Karaoke", colorOutline: "Outline", colorShadow: "Shadow",
    animation: "Animation", position: "Position", marginV: "Margin V",
    wordMode: "Word", sentenceMode: "Sentence",
    resetGlobal: "Reset to global style",
    noSubsHre: "No subtitles in HRE mode — AI handles styling automatically.",
    noSubEvents: "No subtitle lines were generated for this clip. Try re-running with sentence subtitles or render again after the backend update.",
    cut: "Cut",
    demoSession: "Demo session", waitRender: "Waiting for render", close: "Close",
    preview: "PREVIEW",
    demoNotice: "Simulation only — these are pre-rendered demo results, not a live GPU run.",
  },
  th: {
    back: "กลับ", clips: "คลิป", clip: "คลิป",
    duration: "ความยาว", aiScore: "คะแนน AI",
    render: "เรนเดอร์", download: "ดาวน์โหลด", rendering: "กำลังเรนเดอร์…", reRender: "เรนเดอร์ใหม่",
    whyPicked: "เหตุผลที่ AI เลือกคลิปนี้",
    caption: "คำบรรยายแนะนำ", copy: "คัดลอก", copied: "คัดลอกแล้ว",
    trimTab: "ตัด & ตัดกลาง", subsTab: "ซับไตเติ้ล",
    adjustBounds: "ปรับขอบเขต (±10s)", startOff: "ออฟเซ็ตต้น", endOff: "ออฟเซ็ตท้าย",
    cutMiddle: "ตัดกลางคลิป", addCut: "+ เพิ่มจุดตัด",
    noCuts: "ยังไม่มีจุดตัด — กด \"เพิ่มจุดตัด\" เพื่อลบส่วนกลางคลิป",
    totalRemoved: "ตัดออกรวม", finalDuration: "ความยาวสุดท้าย",
    subStyle: "สไตล์ซับ",
    global: "🌐 ทั้งหมด", perLine: "✨ รายบรรทัด",
    styleBtn: "ปรับ ▾", styledBtn: "ปรับแล้ว ▾",
    font: "ฟ้อนต์", size: "ขนาด", outline: "ขอบ", shadow: "เงา",
    colorText: "ตัวอักษร", colorKaraoke: "คาราโอเกะ", colorOutline: "ขอบ", colorShadow: "เงา",
    animation: "อนิเมชั่น", position: "ตำแหน่ง", marginV: "ระยะแนวตั้ง",
    wordMode: "คำต่อคำ", sentenceMode: "ประโยค",
    resetGlobal: "รีเซ็ตเป็นสไตล์ทั่วไป",
    noSubsHre: "HRE mode ไม่มีซับ — AI จัดการสไตล์ให้อัตโนมัติ",
    noSubEvents: "คลิปนี้ยังไม่มีบรรทัดซับ ลองรันใหม่ด้วยซับแบบประโยค หรือเรนเดอร์อีกครั้งหลังอัปเดต backend",
    cut: "จุดตัด",
    demoSession: "Demo session", waitRender: "รอการเรนเดอร์", close: "ปิด",
    preview: "PREVIEW",
    demoNotice: "โหมดจำลองเท่านั้น — คลิปเหล่านี้เป็นผลลัพธ์ที่เตรียมไว้ ไม่ได้รัน GPU สด",
  },
  zh: {
    back: "返回", clips: "片段", clip: "片段",
    duration: "时长", aiScore: "AI分数",
    render: "渲染", download: "下载", rendering: "渲染中…", reRender: "重新渲染",
    whyPicked: "AI选择此片段的原因",
    caption: "建议说明", copy: "复制", copied: "已复制",
    trimTab: "剪辑 & 切割", subsTab: "字幕",
    adjustBounds: "调整边界 (±10s)", startOff: "开始偏移", endOff: "结束偏移",
    cutMiddle: "从中间切割", addCut: "+ 添加切割",
    noCuts: "暂无切割 — 点击\"添加切割\"删除中间部分",
    totalRemoved: "总计删除", finalDuration: "最终时长",
    subStyle: "字幕样式",
    global: "🌐 全局", perLine: "✨ 逐行",
    styleBtn: "样式 ▾", styledBtn: "已设置 ▾",
    font: "字体", size: "大小", outline: "描边", shadow: "阴影",
    colorText: "文字", colorKaraoke: "卡拉OK", colorOutline: "描边", colorShadow: "阴影",
    animation: "动画", position: "位置", marginV: "垂直边距",
    wordMode: "逐词", sentenceMode: "句子",
    resetGlobal: "重置为全局样式",
    noSubsHre: "HRE模式无字幕 — AI自动处理样式",
    noSubEvents: "此片段未生成字幕行。请用句子字幕重新运行，或在后端更新后重新渲染。",
    cut: "切割",
    demoSession: "演示会话", waitRender: "等待渲染", close: "关闭",
    preview: "预览",
    demoNotice: "仅为模拟演示 — 这些是预渲染结果，并非实时 GPU 运行。",
  },
} as const;
type Lbl = typeof L[Lang];

// ─── Mock data ─────────────────────────────────────────────────────────────────
const MOCK_CLIPS: (ClipResult & { suggested_caption: string })[] = [
  {
    index: 0, start: 13.0, end: 43.0, duration: 30.0, score: 0.462,
    download_url: DEMO_CLIP_URLS[0], raw_url: DEMO_CLIP_URLS[0], ass_path: "demo_0.ass",
    highlight_reason: "The speaker is enthusiastically discussing the benefits of the AMD Instinct MI350P, making it a compelling highlight for tech enthusiasts.",
    suggested_caption: "AMD Instinct MI350P explained in 30 seconds: AI infrastructure, performance, and enterprise-ready acceleration.",
  },
  {
    index: 1, start: 125.0, end: 155.0, duration: 30.0, score: 0.45,
    download_url: DEMO_CLIP_URLS[1], raw_url: DEMO_CLIP_URLS[1], ass_path: "demo_1.ass",
    highlight_reason: "The speaker is enthusiastically discussing the benefits of the AMD Instinct MI350P, making it engaging for viewers interested in technology and AI.",
    suggested_caption: "A quick look at how AMD Instinct GPUs power modern AI and high-performance computing workloads.",
  },
  {
    index: 2, start: 149.0, end: 179.0, duration: 30.0, score: 0.398,
    download_url: DEMO_CLIP_URLS[2], raw_url: DEMO_CLIP_URLS[2], ass_path: "demo_2.ass",
    highlight_reason: "The speaker is enthusiastically discussing the benefits of the AMD Instinct MI350P, making it engaging for viewers interested in enterprise computing and AI.",
    suggested_caption: "Enterprise AI needs serious compute. This clip highlights where AMD Instinct fits in the stack.",
  },
];

const MOCK_SUBS: Record<number, SubEvent[]> = {
  0: [
    { index: 0, text: "AMD Instinct MI350P", start: 0.0, end: 2.8 },
    { index: 1, text: "Built for AI acceleration", start: 3.2, end: 5.8 },
    { index: 2, text: "Enterprise compute at scale", start: 7.0, end: 9.6 },
    { index: 3, text: "Vision, audio, and transcript signals combined", start: 12.0, end: 15.0 },
    { index: 4, text: "HRE keeps the important subject visible", start: 20.0, end: 23.4 },
  ],
  1: [
    { index: 0, text: "The key benefit is throughput", start: 0.0, end: 2.8 },
    { index: 1, text: "AI workloads need memory and bandwidth", start: 3.4, end: 6.3 },
    { index: 2, text: "Qwen selected this as a strong technical moment", start: 8.0, end: 11.2 },
    { index: 3, text: "Captions can be edited in the demo", start: 18.0, end: 21.0 },
  ],
  2: [
    { index: 0, text: "Enterprise AI infrastructure", start: 0.0, end: 2.7 },
    { index: 1, text: "The model chooses the most useful 30 seconds", start: 4.0, end: 7.2 },
    { index: 2, text: "Zoom and caption style vary by moment", start: 9.0, end: 12.0 },
    { index: 3, text: "This preview uses pre-rendered demo output", start: 20.0, end: 23.0 },
  ],
};

const LANG_OPTIONS = [
  { code: "en" as Lang, label: "English" },
  { code: "th" as Lang, label: "ไทย" },
  { code: "zh" as Lang, label: "中文" },
];

const FONTS = ["Noto Sans Thai", "Noto Sans SC", "Noto Sans", "Impact", "Montserrat", "Oswald", "Anton"];
const ANIMATIONS = ["none", "fade", "karaoke", "pop", "typewriter", "bounce"];
const ALIGNMENTS = [
  { val: 7, label: "↖" }, { val: 8, label: "↑" }, { val: 9, label: "↗" },
  { val: 4, label: "←" }, { val: 5, label: "·" }, { val: 6, label: "→" },
  { val: 1, label: "↙" }, { val: 2, label: "↓" }, { val: 3, label: "↘" },
];

const ANIM_KEYFRAMES = `
  @keyframes elevn-fade { 0%,100%{opacity:0} 30%,70%{opacity:1} }
  @keyframes elevn-pop { 0%,100%{transform:scale(0.5);opacity:0} 40%{transform:scale(1.12)} 50%,80%{transform:scale(1);opacity:1} }
  @keyframes elevn-bounce { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-9px)} }
  @keyframes elevn-type { from{clip-path:inset(0 100% 0 0)} to{clip-path:inset(0 0% 0 0)} }
`;

// ─── TikTok phone mock preview (180×320) ──────────────────────────────────────
type PreviewStyle = {
  font_family?: string; font_size?: number;
  primary_color?: string; secondary_color?: string;
  outline_color?: string; outline_size?: number;
  bold?: boolean; italic?: boolean; animation?: string;
  alignment?: number; margin_v?: number;
};

function TikTokMiniPreview({ style, text, lbl }: { style: PreviewStyle; text: string; lbl: Lbl }) {
  const alignment = style.alignment ?? 2;
  const isBottom = alignment <= 3;
  const isTop    = alignment >= 7;
  const isLeft   = [1, 4, 7].includes(alignment);
  const isRight  = [3, 6, 9].includes(alignment);

  const s = 0.34;
  const fontSize  = Math.max(10, (style.font_size ?? 52) * s);
  const outlineW  = (style.outline_size ?? 2.5) * s;
  const textShadow = outlineW > 0
    ? `${outlineW}px ${outlineW}px 0 ${style.outline_color ?? "#000"},
       -${outlineW}px ${outlineW}px 0 ${style.outline_color ?? "#000"},
       ${outlineW}px -${outlineW}px 0 ${style.outline_color ?? "#000"},
       -${outlineW}px -${outlineW}px 0 ${style.outline_color ?? "#000"}`
    : "none";

  const animMap: Record<string, string> = {
    fade: "elevn-fade 2s ease-in-out infinite",
    pop:  "elevn-pop 1.8s ease-in-out infinite",
    bounce: "elevn-bounce 1s ease-in-out infinite",
    typewriter: "elevn-type 2.5s steps(20) infinite",
  };

  const posStyle: React.CSSProperties = {
    position: "absolute", zIndex: 10, maxWidth: "76%", wordBreak: "break-word",
    textAlign: isLeft ? "left" : isRight ? "right" : "center",
  };
  if (isBottom) {
    posStyle.bottom = "18%";
    posStyle.left  = isLeft ? "4%" : isRight ? undefined : "12%";
    posStyle.right = isRight ? "14%" : isLeft ? undefined : "12%";
  } else if (isTop) {
    posStyle.top  = "12%";
    posStyle.left  = isLeft ? "4%" : isRight ? undefined : "12%";
    posStyle.right = isRight ? "14%" : isLeft ? undefined : "12%";
  } else {
    posStyle.top = "50%"; posStyle.transform = "translateY(-50%)";
    posStyle.left  = isLeft ? "4%" : isRight ? undefined : "12%";
    posStyle.right = isRight ? "14%" : isLeft ? undefined : "12%";
  }

  const textStyle: React.CSSProperties = {
    fontFamily: `"${style.font_family ?? "Noto Sans"}", sans-serif`,
    fontSize: `${fontSize}px`,
    fontWeight: style.bold ?? true ? "bold" : "normal",
    fontStyle: style.italic ? "italic" : "normal",
    color: style.primary_color ?? "#FFFFFF",
    textShadow, lineHeight: 1.25,
    animation: animMap[style.animation ?? ""] ?? "none",
    display: "inline-block",
  };

  return (
    <div className="relative rounded-3xl overflow-hidden shadow-2xl border-4 border-gray-700 bg-black"
      style={{ width: 180, height: 320 }}>
      <style>{ANIM_KEYFRAMES}</style>
      <div className="absolute inset-0 bg-gradient-to-br from-slate-900 via-purple-950 to-slate-900" />
      {/* Grid lines */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute" style={{ top: "30%", left: 0, right: 0, height: 1, background: "rgba(255,255,255,0.04)" }} />
        <div className="absolute" style={{ top: "60%", left: 0, right: 0, height: 1, background: "rgba(255,255,255,0.04)" }} />
      </div>
      {/* Notch */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-14 h-4 bg-black rounded-b-xl z-20" />
      {/* Side action buttons */}
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
      {/* Bottom info */}
      <div className="absolute left-2 right-12 z-10" style={{ bottom: "8%" }}>
        <div className="text-white text-[9px] font-bold drop-shadow-md">@elevnclip_ai</div>
        <div className="text-white/75 text-[7.5px] mt-0.5 leading-tight drop-shadow">#highlight #tiktok #ai #amd</div>
      </div>
      {/* Progress bar */}
      <div className="absolute bottom-0 left-0 right-0 h-1 bg-white/20 z-10">
        <div className="h-full bg-white/70 w-2/5" />
      </div>
      {/* Subtitle text */}
      <div style={posStyle}><span style={textStyle}>{text || "Sample subtitle"}</span></div>
      {/* Preview badge */}
      <div className="absolute top-6 left-2 z-20">
        <span className="text-[7px] text-white/35 font-mono tracking-widest">{lbl.preview}</span>
      </div>
    </div>
  );
}

// ─── Main content ─────────────────────────────────────────────────────────────
function EditorContent() {
  const params    = useSearchParams();
  const router    = useRouter();
  const sessionId = params.get("session") ?? "";
  const isDemo    = sessionId === "demo";

  const [uiLang, setUiLang] = useState<Lang>("en");
  const lbl = L[uiLang];

  useEffect(() => {
    const saved = localStorage.getItem("elevnclip-lang") as Lang | null;
    if (saved && (["en", "th", "zh"] as string[]).includes(saved)) setUiLang(saved);
  }, []);

  const handleLangChange = (lang: Lang) => {
    setUiLang(lang);
    localStorage.setItem("elevnclip-lang", lang);
  };

  const [clips, setClips]     = useState<(ClipResult & { suggested_caption?: string })[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState("");
  const [activeClip, setActiveClip] = useState(0);
  const [rendering,  setRendering]  = useState<Record<number, boolean>>({});
  const [renderDone, setRenderDone] = useState<Record<number, boolean>>({});
  const [downloadUrls, setDownloadUrls] = useState<Record<number, string>>({});

  const [trimStart,   setTrimStart]   = useState<Record<number, number>>({});
  const [trimEnd,     setTrimEnd]     = useState<Record<number, number>>({});
  const [cutRegions,  setCutRegions]  = useState<Record<number, CutRegion[]>>({});

  const [globalStyle, setGlobalStyle] = useState<StyleConfig>({
    font_family: "Noto Sans", font_size: 64,
    primary_color: "#FFFFFF", secondary_color: "#FFFF00",
    outline_color: "#000000", shadow_color: "#000000",
    bold: true, italic: false, underline: false,
    outline_size: 3.0, shadow_size: 1.5,
    alignment: 2, margin_v: 250,
    display_mode: "word", animation: "pop",
  });

  const [openColorPicker,  setOpenColorPicker]  = useState<string | null>(null);
  const [activeTab,        setActiveTab]        = useState<"trim" | "timeline">("trim");
  const [subEvents,        setSubEvents]        = useState<SubEvent[]>([]);
  const [subStyles,        setSubStyles]        = useState<Record<string, Partial<SubLineStyle>>>({});
  const [expandedSubLine,  setExpandedSubLine]  = useState<number | null>(null);
  const [styleMode,        setStyleMode]        = useState<"global" | "per-line">("global");
  const [copied,           setCopied]           = useState(false);

  useEffect(() => {
    if (!sessionId) { router.push("/"); return; }
    loadClips();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  useEffect(() => {
    if (isDemo) {
      setSubEvents(MOCK_SUBS[activeClip] ?? []);
    } else {
      setSubEvents(clips[activeClip]?.subtitle_events ?? []);
    }
    setExpandedSubLine(null);
  }, [activeClip, clips, isDemo]);

  const loadClips = async () => {
    if (isDemo) {
      setClips(MOCK_CLIPS);
      const urls: Record<number, string> = {};
      MOCK_CLIPS.forEach((c) => { urls[c.index] = c.download_url; });
      setDownloadUrls(urls);
      setSubEvents(MOCK_SUBS[0] ?? []);
      setLoading(false);
      return;
    }
    try {
      const result = await getClips(sessionId);
      if (result.status === "error") { setError(result.error ?? "Failed to load clips"); return; }
      setClips(result.clips);
      const urls: Record<number, string> = {};
      result.clips.forEach((c) => { urls[c.index] = c.download_url; });
      setDownloadUrls(urls);
      setSubEvents(result.clips[0]?.subtitle_events ?? []);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load clips");
    } finally {
      setLoading(false);
    }
  };

  const handleStyleChange = async (updates: Partial<StyleConfig>) => {
    const newStyle = { ...globalStyle, ...updates };
    setGlobalStyle(newStyle);
    if (isDemo) return;
    const clip = clips[activeClip];
    if (clip?.ass_path) await patchGlobalStyle(sessionId, clip.index, newStyle).catch(() => {});
  };

  const handleRender = async (clipIndex: number) => {
    setRendering((r) => ({ ...r, [clipIndex]: true }));
    setRenderDone((d) => ({ ...d, [clipIndex]: false }));
    if (isDemo) {
      await new Promise((r) => setTimeout(r, 1400));
      setRendering((r) => ({ ...r, [clipIndex]: false }));
      setRenderDone((d) => ({ ...d, [clipIndex]: true }));
      return;
    }
    try {
      const url = await renderClip(sessionId, clipIndex);
      setDownloadUrls((d) => ({ ...d, [clipIndex]: url }));
      setRenderDone((d) => ({ ...d, [clipIndex]: true }));
    } catch (e) {
      console.error("Render failed", e);
    } finally {
      setRendering((r) => ({ ...r, [clipIndex]: false }));
    }
  };

  const handleDownload = async () => {
    if (!clipDownloadUrl || !clip) return;
    const a = document.createElement("a");
    a.href = clipDownloadUrl;
    a.download = `clip_${clip.index}.mp4`;
    a.rel = "noopener";
    document.body.appendChild(a);
    a.click();
    a.remove();
  };

  const handleSubEdit = async (clipIndex: number, eventIdx: number, text: string) => {
    setSubEvents((evts) => evts.map((e) => e.index === eventIdx ? { ...e, text } : e));
    if (isDemo) return;
    await patchSubtitle(sessionId, clipIndex, eventIdx, { text }).catch(() => {});
  };

  const handleSubTiming = async (clipIndex: number, eventIdx: number, start: number, end: number) => {
    setSubEvents((evts) => evts.map((e) => e.index === eventIdx ? { ...e, start, end } : e));
    if (isDemo) return;
    await patchSubtitle(sessionId, clipIndex, eventIdx, { start, end }).catch(() => {});
  };

  const handleSubLineStyle = (clipIndex: number, eventIdx: number, updates: Partial<SubLineStyle>) => {
    const key = `${clipIndex}-${eventIdx}`;
    setSubStyles((prev) => ({ ...prev, [key]: { ...prev[key], ...updates } }));
  };

  const handleResetSubLine = (clipIndex: number, eventIdx: number) => {
    const key = `${clipIndex}-${eventIdx}`;
    setSubStyles((prev) => { const next = { ...prev }; delete next[key]; return next; });
  };

  const addCut = (clipIndex: number, duration: number) => {
    const existing = cutRegions[clipIndex] ?? [];
    setCutRegions((prev) => ({
      ...prev,
      [clipIndex]: [...existing, { id: Date.now(), from: parseFloat((duration * 0.3).toFixed(1)), to: parseFloat((duration * 0.5).toFixed(1)) }],
    }));
  };
  const removeCut = (clipIndex: number, cutId: number) => {
    setCutRegions((prev) => ({ ...prev, [clipIndex]: (prev[clipIndex] ?? []).filter((c) => c.id !== cutId) }));
  };
  const updateCut = (clipIndex: number, cutId: number, from: number, to: number) => {
    setCutRegions((prev) => ({
      ...prev,
      [clipIndex]: (prev[clipIndex] ?? []).map((c) => c.id === cutId ? { ...c, from, to } : c),
    }));
  };

  const handleCopyCaption = (text: string) => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true); setTimeout(() => setCopied(false), 2000);
    });
  };

  if (loading) return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-center space-y-3">
        <Loader2 size={32} className="animate-spin mx-auto text-violet-400" />
        <p className="text-white/50">Loading clips...</p>
      </div>
    </div>
  );

  if (error) return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-center space-y-4">
        <p className="text-red-400 text-sm">{error}</p>
        <button onClick={() => router.push("/")} className="px-6 py-2 bg-violet-600 rounded-xl text-white text-sm">Back to Home</button>
      </div>
    </div>
  );

  const clip = clips[activeClip];
  const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  const rawUrl = clip ? (downloadUrls[clip.index] ?? clip.download_url) : "";
  const clipDownloadUrl = isDemo
    ? rawUrl
    : rawUrl.startsWith("http") ? rawUrl : rawUrl ? `${apiBase}${rawUrl}` : "";
  const suggestedCaption = (clip as (typeof clip & { suggested_caption?: string }))?.suggested_caption;
  const currentCuts  = clip ? (cutRegions[clip.index] ?? []) : [];
  const clipDuration = clip ? clip.duration + (trimEnd[clip.index] ?? 0) - (trimStart[clip.index] ?? 0) : 60;

  // TikTok preview style: in per-line mode, use expanded line's effective style
  const expandedEvent    = subEvents.find((e) => e.index === expandedSubLine);
  const expandedOverride = (expandedSubLine !== null && clip) ? subStyles[`${clip.index}-${expandedSubLine}`] ?? {} : {};
  const previewStyle: PreviewStyle = styleMode === "per-line" && expandedSubLine !== null
    ? { ...globalStyle, ...expandedOverride }
    : globalStyle;
  const previewText = styleMode === "per-line" && expandedEvent ? expandedEvent.text : "Sample subtitle";

  return (
    <div className="h-screen flex flex-col overflow-hidden">
      {/* ── Navbar ── */}
      <nav className="border-b border-white/10 px-5 py-2.5 flex items-center justify-between bg-black/30 backdrop-blur shrink-0 z-40">
        <div className="flex items-center gap-3">
          <button onClick={() => router.push("/")} className="text-white/50 hover:text-white transition text-sm flex items-center gap-1.5">
            <ChevronLeft size={14} /> {lbl.back}
          </button>
          <span className="text-white/20">|</span>
          <div className="flex items-center gap-2">
            <Scissors size={14} className="text-violet-400" />
            <span className="font-semibold text-sm">Clip Editor</span>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {/* Language switcher */}
          <div className="flex gap-1">
            {LANG_OPTIONS.map((l) => (
              <button key={l.code} onClick={() => handleLangChange(l.code)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${uiLang === l.code ? "bg-violet-600 text-white" : "text-white/40 hover:text-white hover:bg-white/10"}`}>
                {l.label}
              </button>
            ))}
          </div>
          <span className="text-xs text-white/30">
            {clips.length} {lbl.clips.toLowerCase()} · {isDemo ? lbl.demoSession : `Session: ${sessionId.slice(0, 8)}…`}
          </span>
        </div>
      </nav>
      {isDemo && (
        <div className="border-b border-cyan-400/20 bg-cyan-400/10 px-5 py-2 text-center text-xs text-cyan-100">
          {lbl.demoNotice}
        </div>
      )}

      {/* ── Main layout ── */}
      <div className="flex flex-1 min-h-0 overflow-hidden">

        {/* ── Clip list sidebar ── */}
        <div className="w-36 border-r border-white/10 flex flex-col bg-black/20 shrink-0 overflow-y-auto">
          <div className="px-3 py-2 text-xs text-white/30 font-medium uppercase tracking-wider">{lbl.clips}</div>
          {clips.map((c, i) => (
            <button key={c.index} onClick={() => setActiveClip(i)}
              className={`px-3 py-2.5 text-left border-b border-white/5 transition ${activeClip === i ? "bg-violet-600/20 border-l-2 border-l-violet-500" : "hover:bg-white/5"}`}>
              <div className="font-medium text-xs text-white">{lbl.clip} {c.index + 1}</div>
              <div className="text-[10px] text-white/40 mt-0.5">{c.start.toFixed(1)}s – {c.end.toFixed(1)}s</div>
              <div className="flex items-center gap-1 mt-1">
                <div className="h-1 flex-1 bg-white/10 rounded-full overflow-hidden">
                  <div className="h-full bg-violet-500 rounded-full" style={{ width: `${(c.score ?? 0) * 100}%` }} />
                </div>
                <span className="text-[10px] text-violet-300">{((c.score ?? 0) * 100).toFixed(0)}%</span>
              </div>
            </button>
          ))}
        </div>

        {/* ── Video — fixed width, left-aligned ── */}
        <div className="w-[360px] shrink-0 border-r border-white/10 flex flex-col bg-black/40 p-3 gap-2">
          <div className="w-full relative bg-black rounded-2xl overflow-hidden shadow-2xl" style={{ aspectRatio: "9/16" }}>
            {clipDownloadUrl ? (
              <video
                key={clipDownloadUrl}
                src={clipDownloadUrl}
                controls
                className="absolute inset-0 w-full h-full object-cover"
              />
            ) : (
              <div className="absolute inset-0 bg-gradient-to-br from-slate-900 via-purple-950 to-slate-900 flex flex-col items-center justify-center gap-2">
                <Loader2 size={24} className="animate-spin text-violet-400" />
                <p className="text-white/30 text-xs">{lbl.waitRender}</p>
              </div>
            )}
          </div>
          {/* Stats */}
          <div className="flex items-center justify-between text-[10px] text-white/30 px-1">
            <span>{lbl.duration} <span className="text-white/60">{clip?.duration.toFixed(1)}s</span></span>
            <span className="text-violet-300">{((clip?.score ?? 0) * 100).toFixed(0)}%</span>
          </div>
        </div>

        {/* ── Right panel — fills remaining space ── */}
        <div className="flex-1 min-w-0 overflow-y-auto p-4 space-y-3">

          {/* Render + Download */}
          <div className="flex gap-2">
            {clip?.ass_path && (
              <button onClick={() => handleRender(clip.index)} disabled={rendering[clip.index]}
                className="flex-1 flex items-center justify-center gap-2 py-2.5 bg-violet-600 hover:bg-violet-700 disabled:opacity-50 rounded-xl text-sm font-semibold transition text-white">
                {rendering[clip.index]
                  ? <><Loader2 size={14} className="animate-spin" /> {lbl.rendering}</>
                  : renderDone[clip.index]
                  ? <><CheckCircle2 size={14} className="text-green-300" /> {lbl.reRender}</>
                  : <><RotateCcw size={14} /> {lbl.render}</>}
              </button>
            )}
            <button
              type="button"
              onClick={handleDownload}
              disabled={!clipDownloadUrl}
              className={`flex-1 flex items-center justify-center gap-2 py-2.5 rounded-xl text-sm font-semibold transition text-white ${
                clipDownloadUrl ? "bg-white/10 hover:bg-white/20 cursor-pointer" : "bg-white/5 opacity-40 cursor-not-allowed"
              }`}>
              <Download size={14} /> {lbl.download}
            </button>
          </div>

          {/* AI reason */}
          {clip?.highlight_reason && (
            <div className="bg-violet-500/10 border border-violet-500/20 rounded-xl px-4 py-2.5 text-sm text-violet-200 flex items-start gap-2">
              <Bot size={15} className="shrink-0 mt-0.5 text-violet-400" />
              <div>
                <div className="text-xs text-violet-400 font-medium mb-0.5">{lbl.whyPicked}</div>
                {clip.highlight_reason}
              </div>
            </div>
          )}

          {/* Suggested caption */}
          {suggestedCaption && (
            <div className="bg-white/5 border border-white/10 rounded-xl px-4 py-2.5">
              <div className="flex items-center justify-between mb-1.5">
                <div className="flex items-center gap-1.5 text-xs text-white/50 font-medium">
                  <FileText size={12} /> {lbl.caption}
                </div>
                <button onClick={() => handleCopyCaption(suggestedCaption)}
                  className="flex items-center gap-1 text-xs text-white/40 hover:text-white transition">
                  {copied ? <><Check size={11} className="text-green-400" /> {lbl.copied}</> : <><Copy size={11} /> {lbl.copy}</>}
                </button>
              </div>
              <p className="text-sm text-white/80 leading-relaxed">{suggestedCaption}</p>
            </div>
          )}

          {/* Tabs */}
          <div className="flex gap-1 bg-white/5 rounded-xl p-1">
            {(["trim", "timeline"] as const).map((t) => (
              <button key={t} onClick={() => setActiveTab(t)}
                className={`flex-1 py-1.5 rounded-lg text-xs font-medium transition ${activeTab === t ? "bg-violet-600 text-white" : "text-white/50 hover:text-white"}`}>
                {t === "trim" ? lbl.trimTab : lbl.subsTab}
              </button>
            ))}
          </div>

          {/* ── Trim & Cut tab ── */}
          {activeTab === "trim" && clip && (
            <div className="space-y-4">
              {/* Start/End offset */}
              <div className="bg-white/5 border border-white/10 rounded-2xl p-4 space-y-3">
                <h3 className="font-medium text-xs text-white/60 uppercase tracking-wider">{lbl.adjustBounds}</h3>
                {[
                  { key: "start", label: lbl.startOff, value: trimStart[clip.index] ?? 0, setter: setTrimStart },
                  { key: "end",   label: lbl.endOff,   value: trimEnd[clip.index] ?? 0,   setter: setTrimEnd },
                ].map(({ key, label, value, setter }) => (
                  <div key={key}>
                    <label className="text-xs text-white/50">{label} ({value >= 0 ? "+" : ""}{value}s)</label>
                    <input type="range" min={-10} max={10} step={0.5} value={value}
                      onChange={(e) => setter((t) => ({ ...t, [clip.index]: +e.target.value }))}
                      className="w-full mt-1" />
                    <div className="flex justify-between text-[10px] text-white/25"><span>-10s</span><span>0</span><span>+10s</span></div>
                  </div>
                ))}
              </div>

              {/* Cut regions */}
              <div className="bg-white/5 border border-white/10 rounded-2xl p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="font-medium text-xs text-white/60 uppercase tracking-wider flex items-center gap-1.5">
                    <ScissorsIcon size={11} /> {lbl.cutMiddle}
                  </h3>
                  <button onClick={() => addCut(clip.index, clipDuration)}
                    className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-white/10 hover:bg-violet-600 text-white/60 hover:text-white text-xs transition">
                    <Plus size={11} /> {lbl.addCut}
                  </button>
                </div>

                {clipDuration > 0 && (
                  <div className="relative h-5 bg-white/10 rounded-full overflow-hidden">
                    <div className="absolute inset-0 flex items-center justify-center">
                      <span className="text-[9px] text-white/20 pointer-events-none">{clipDuration.toFixed(1)}s</span>
                    </div>
                    {(trimStart[clip.index] ?? 0) > 0 && (
                      <div className="absolute left-0 top-0 bottom-0 bg-violet-500/30"
                        style={{ width: `${((trimStart[clip.index] ?? 0) / clipDuration) * 100}%` }} />
                    )}
                    {(trimEnd[clip.index] ?? 0) < 0 && (
                      <div className="absolute right-0 top-0 bottom-0 bg-violet-500/30"
                        style={{ width: `${(Math.abs(trimEnd[clip.index] ?? 0) / clipDuration) * 100}%` }} />
                    )}
                    {currentCuts.map((cut) => (
                      <div key={cut.id} className="absolute top-0 bottom-0 bg-red-500/50 border-x border-red-400"
                        style={{
                          left: `${Math.min(100, (cut.from / clipDuration) * 100)}%`,
                          width: `${Math.max(1, ((cut.to - cut.from) / clipDuration) * 100)}%`,
                        }} />
                    ))}
                  </div>
                )}

                {currentCuts.length === 0 && (
                  <p className="text-xs text-white/25 text-center">{lbl.noCuts}</p>
                )}

                {currentCuts.map((cut, ci) => (
                  <div key={cut.id} className="flex items-center gap-2 bg-white/5 rounded-xl px-3 py-2">
                    <span className="text-[10px] text-white/40 shrink-0">{(lbl as typeof L["en"]).cut ?? "Cut"} {ci + 1}</span>
                    <div className="flex items-center gap-1.5 flex-1">
                      <input type="number" step={0.1} min={0} max={clipDuration} value={cut.from}
                        onChange={(e) => updateCut(clip.index, cut.id, +e.target.value, cut.to)}
                        className="flex-1 bg-white/5 border border-white/10 rounded px-2 py-1 text-xs text-white font-mono focus:outline-none focus:border-violet-500" />
                      <span className="text-white/30 text-xs shrink-0">s →</span>
                      <input type="number" step={0.1} min={0} max={clipDuration} value={cut.to}
                        onChange={(e) => updateCut(clip.index, cut.id, cut.from, +e.target.value)}
                        className="flex-1 bg-white/5 border border-white/10 rounded px-2 py-1 text-xs text-white font-mono focus:outline-none focus:border-violet-500" />
                      <span className="text-white/30 text-xs shrink-0">s</span>
                    </div>
                    <span className="text-[10px] text-white/30 shrink-0">({(cut.to - cut.from).toFixed(1)}s)</span>
                    <button onClick={() => removeCut(clip.index, cut.id)}
                      className="text-white/30 hover:text-red-400 transition shrink-0 p-0.5">
                      <X size={13} />
                    </button>
                  </div>
                ))}

                {currentCuts.length > 0 && (
                  <p className="text-xs text-white/30">
                    {lbl.totalRemoved}: {currentCuts.reduce((sum, c) => sum + Math.max(0, c.to - c.from), 0).toFixed(1)}s ·
                    {" "}{lbl.finalDuration}: {(clipDuration - currentCuts.reduce((sum, c) => sum + Math.max(0, c.to - c.from), 0)).toFixed(1)}s
                  </p>
                )}
              </div>
            </div>
          )}

          {/* ── Subtitles tab — TikTok preview on left ── */}
          {activeTab === "timeline" && clip?.ass_path && (
            <div className="flex gap-3 items-start">
              {/* Left: TikTok mock preview — sticky while scrolling event list */}
              <div className="shrink-0 sticky top-4">
                <TikTokMiniPreview style={previewStyle} text={previewText} lbl={lbl} />
              </div>
              {/* Right: controls */}
              <div className="flex-1 min-w-0">
                <SubtitleTimelinePanel
                  clipIndex={clip.index}
                  events={subEvents}
                  globalStyle={globalStyle}
                  subStyles={subStyles}
                  expandedLine={expandedSubLine}
                  styleMode={styleMode}
                  openColorPicker={openColorPicker}
                  lbl={lbl}
                  onExpand={setExpandedSubLine}
                  onEdit={handleSubEdit}
                  onTiming={handleSubTiming}
                  onLineStyle={handleSubLineStyle}
                  onResetLine={handleResetSubLine}
                  onGlobalStyle={handleStyleChange}
                  onStyleMode={setStyleMode}
                  onColorPicker={setOpenColorPicker}
                />
              </div>
            </div>
          )}

          {activeTab === "timeline" && !clip?.ass_path && (
            <div className="bg-white/5 border border-white/10 rounded-2xl p-4 text-center text-white/40 text-sm">
              {lbl.noSubsHre}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Subtitle Timeline Panel ──────────────────────────────────────────────────
function SubtitleTimelinePanel({
  clipIndex, events, globalStyle, subStyles, expandedLine, styleMode,
  openColorPicker, lbl, onExpand, onEdit, onTiming, onLineStyle, onResetLine,
  onGlobalStyle, onStyleMode, onColorPicker,
}: {
  clipIndex: number; events: SubEvent[]; globalStyle: StyleConfig;
  subStyles: Record<string, Partial<SubLineStyle>>;
  expandedLine: number | null; styleMode: "global" | "per-line";
  openColorPicker: string | null; lbl: Lbl;
  onExpand: (i: number | null) => void;
  onEdit: (ci: number, ei: number, text: string) => void;
  onTiming: (ci: number, ei: number, start: number, end: number) => void;
  onLineStyle: (ci: number, ei: number, updates: Partial<SubLineStyle>) => void;
  onResetLine: (ci: number, ei: number) => void;
  onGlobalStyle: (updates: Partial<StyleConfig>) => void;
  onStyleMode: (m: "global" | "per-line") => void;
  onColorPicker: (k: string | null) => void;
}) {
  return (
    <div className="space-y-3">
      {/* Style mode toggle + global controls */}
      <div className="bg-white/5 border border-white/10 rounded-2xl p-3 space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium text-white/60">{lbl.subStyle}</span>
          <div className="flex gap-1 bg-white/10 rounded-lg p-0.5">
            <button onClick={() => onStyleMode("global")}
              className={`px-3 py-1 rounded-md text-xs font-medium transition ${styleMode === "global" ? "bg-violet-600 text-white" : "text-white/40 hover:text-white"}`}>
              {lbl.global}
            </button>
            <button onClick={() => onStyleMode("per-line")}
              className={`px-3 py-1 rounded-md text-xs font-medium transition ${styleMode === "per-line" ? "bg-violet-600 text-white" : "text-white/40 hover:text-white"}`}>
              {lbl.perLine}
            </button>
          </div>
        </div>
        {styleMode === "global" && (
          <GlobalStyleControls style={globalStyle} lbl={lbl}
            onChange={onGlobalStyle}
            openColorPicker={openColorPicker}
            setOpenColorPicker={onColorPicker} />
        )}
      </div>

      {/* Events list */}
      <div className="space-y-2">
        {events.length === 0 && (
          <div className="rounded-2xl border border-amber-400/20 bg-amber-400/10 p-3 text-sm text-amber-100">
            {lbl.noSubEvents}
          </div>
        )}
        {events.map((evt) => {
          const styleKey   = `${clipIndex}-${evt.index}`;
          const lineStyle  = subStyles[styleKey] ?? {};
          const hasOverride = Object.keys(lineStyle).length > 0;
          const isExpanded  = expandedLine === evt.index;

          return (
            <div key={evt.index}
              className={`rounded-2xl border transition-all ${isExpanded ? "border-violet-500/50 bg-violet-500/5" : "border-white/10 bg-white/5"}`}>
              <div className="p-3 space-y-2">
                <div className="flex items-start gap-2">
                  <span className="text-[10px] text-white/25 font-mono mt-1 shrink-0 w-4">{evt.index + 1}</span>
                  <input value={evt.text}
                    onChange={(e) => onEdit(clipIndex, evt.index, e.target.value)}
                    className="flex-1 bg-transparent text-sm text-white focus:outline-none border-b border-white/15 focus:border-violet-500 pb-0.5 transition" />
                  {styleMode === "per-line" && (
                    <button onClick={() => onExpand(isExpanded ? null : evt.index)}
                      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold transition shrink-0 ${
                        isExpanded
                          ? "bg-violet-600 text-white"
                          : hasOverride
                          ? "bg-violet-500/20 text-violet-300 border border-violet-500/50 hover:bg-violet-600 hover:text-white"
                          : "bg-white/10 text-white/60 hover:bg-violet-600/60 hover:text-white"
                      }`}>
                      <Palette size={12} />
                      {hasOverride ? lbl.styledBtn : lbl.styleBtn}
                    </button>
                  )}
                </div>
                <div className="flex items-center gap-2 pl-6">
                  <div className="flex items-center gap-1 flex-1">
                    <span className="text-[10px] text-white/30 w-5">{lbl.font.slice(0,2) === "ฟ้" ? "เข้า" : "In"}</span>
                    <input type="number" step={0.1} min={0} value={evt.start.toFixed(2)}
                      onChange={(e) => onTiming(clipIndex, evt.index, +e.target.value, evt.end)}
                      className="flex-1 bg-white/5 border border-white/10 rounded px-1.5 py-0.5 text-[11px] text-white font-mono focus:outline-none focus:border-violet-500" />
                  </div>
                  <span className="text-white/20 text-xs">→</span>
                  <div className="flex items-center gap-1 flex-1">
                    <span className="text-[10px] text-white/30 w-5">{lbl.font.slice(0,2) === "ฟ้" ? "ออก" : "Out"}</span>
                    <input type="number" step={0.1} min={0} value={evt.end.toFixed(2)}
                      onChange={(e) => onTiming(clipIndex, evt.index, evt.start, +e.target.value)}
                      className="flex-1 bg-white/5 border border-white/10 rounded px-1.5 py-0.5 text-[11px] text-white font-mono focus:outline-none focus:border-violet-500" />
                  </div>
                  <span className="text-[10px] text-white/25 shrink-0">{(evt.end - evt.start).toFixed(1)}s</span>
                </div>
              </div>

              {styleMode === "per-line" && isExpanded && (
                <div className="border-t border-white/10 p-3">
                  <PerLineStyleControls
                    lineStyle={lineStyle} globalStyle={globalStyle} text={evt.text}
                    hasOverride={hasOverride} lbl={lbl}
                    onChange={(updates) => onLineStyle(clipIndex, evt.index, updates)}
                    onReset={() => onResetLine(clipIndex, evt.index)}
                  />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Global style controls ────────────────────────────────────────────────────
function GlobalStyleControls({ style, lbl, onChange, openColorPicker, setOpenColorPicker }: {
  style: StyleConfig; lbl: Lbl;
  onChange: (s: Partial<StyleConfig>) => void;
  openColorPicker: string | null;
  setOpenColorPicker: (k: string | null) => void;
}) {
  const colorFields = [
    { key: "primary_color",   label: lbl.colorText },
    { key: "secondary_color", label: lbl.colorKaraoke },
    { key: "outline_color",   label: lbl.colorOutline },
    { key: "shadow_color",    label: lbl.colorShadow },
  ];

  return (
    <div className="space-y-3 pt-1">
      {/* Font + Size */}
      <div className="grid grid-cols-2 gap-2">
        <div className="space-y-1">
          <label className="text-[11px] text-white/50">{lbl.font}</label>
          <select value={style.font_family} onChange={(e) => onChange({ font_family: e.target.value })}
            className="w-full bg-white/5 border border-white/20 rounded-lg px-2 py-1.5 text-xs text-white focus:outline-none focus:border-violet-500">
            {FONTS.map((f) => <option key={f} value={f} className="bg-gray-900">{f}</option>)}
          </select>
        </div>
        <div className="space-y-1">
          <label className="text-[11px] text-white/50">{lbl.size} ({style.font_size}px)</label>
          <input type="range" min={20} max={96} step={2} value={style.font_size}
            onChange={(e) => onChange({ font_size: +e.target.value })} className="w-full mt-2" />
        </div>
        <div className="space-y-1">
          <label className="text-[11px] text-white/50">{lbl.outline} ({style.outline_size}px)</label>
          <input type="range" min={0} max={10} step={0.5} value={style.outline_size}
            onChange={(e) => onChange({ outline_size: +e.target.value })} className="w-full mt-2" />
        </div>
        <div className="space-y-1">
          <label className="text-[11px] text-white/50">{lbl.shadow} ({style.shadow_size}px)</label>
          <input type="range" min={0} max={10} step={0.5} value={style.shadow_size}
            onChange={(e) => onChange({ shadow_size: +e.target.value })} className="w-full mt-2" />
        </div>
      </div>

      {/* B/I/U + display mode */}
      <div className="flex gap-1.5 flex-wrap">
        {[{ k: "bold", l: "B" }, { k: "italic", l: "I" }, { k: "underline", l: "U" }].map(({ k, l }) => (
          <button key={k} onClick={() => onChange({ [k]: !(style as Record<string, unknown>)[k] })}
            className={`w-8 h-8 rounded-lg border text-sm transition ${(style as Record<string, unknown>)[k] ? "border-violet-500 bg-violet-600 text-white" : "border-white/20 bg-white/5 text-white/50 hover:text-white"}`}>
            {l}
          </button>
        ))}
        <div className="h-8 w-px bg-white/10" />
        {[{ id: "word", label: lbl.wordMode }, { id: "sentence", label: lbl.sentenceMode }].map(({ id, label }) => (
          <button key={id} onClick={() => onChange({ display_mode: id as "word" | "sentence" })}
            className={`px-2.5 py-1 rounded-lg text-xs font-medium transition ${style.display_mode === id ? "bg-violet-600 text-white" : "bg-white/5 text-white/50 border border-white/10 hover:text-white"}`}>
            {label}
          </button>
        ))}
      </div>

      {/* Colors */}
      <div className="grid grid-cols-4 gap-1.5">
        {colorFields.map(({ key, label }) => (
          <div key={key} className="relative">
            <button onClick={() => setOpenColorPicker(openColorPicker === key ? null : key)}
              className="w-full flex flex-col items-center gap-1 p-1.5 rounded-xl border border-white/10 hover:border-violet-400 transition bg-white/5">
              <span className="w-7 h-7 rounded-lg border border-white/20 block" style={{ background: (style as Record<string, string>)[key] ?? "#fff" }} />
              <span className="text-[9px] text-white/50 text-center leading-none">{label}</span>
            </button>
            {openColorPicker === key && (
              <div className="absolute z-50 top-full mt-1 left-0">
                <div className="p-2 bg-gray-900 border border-white/20 rounded-xl shadow-2xl">
                  <HexColorPicker color={(style as Record<string, string>)[key] ?? "#fff"}
                    onChange={(c) => onChange({ [key]: c })} />
                  <button onClick={() => setOpenColorPicker(null)} className="mt-2 w-full text-xs text-white/40 hover:text-white">{lbl.close}</button>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Animation */}
      <div className="space-y-1.5">
        <label className="text-[11px] text-white/50">{lbl.animation}</label>
        <div className="grid grid-cols-3 gap-1">
          {ANIMATIONS.map((a) => (
            <button key={a} onClick={() => onChange({ animation: a as StyleConfig["animation"] })}
              className={`py-1.5 rounded-lg text-xs capitalize transition ${style.animation === a ? "bg-violet-600 text-white" : "bg-white/5 text-white/50 border border-white/10 hover:text-white"}`}>
              {a}
            </button>
          ))}
        </div>
      </div>

      {/* Position */}
      <div className="flex items-start gap-4">
        <div className="space-y-1.5">
          <label className="text-[11px] text-white/50">{lbl.position}</label>
          <div className="grid grid-cols-3 gap-0.5 w-20">
            {ALIGNMENTS.map((a) => (
              <button key={a.val} onClick={() => onChange({ alignment: a.val })}
                className={`aspect-square rounded text-xs font-bold transition ${style.alignment === a.val ? "bg-violet-600 text-white" : "bg-white/10 text-white/50 hover:bg-white/20"}`}>
                {a.label}
              </button>
            ))}
          </div>
        </div>
        <div className="flex-1 space-y-1">
          <label className="text-[11px] text-white/50">{lbl.marginV} ({style.margin_v}px)</label>
          <input type="range" min={0} max={200} step={5} value={style.margin_v}
            onChange={(e) => onChange({ margin_v: +e.target.value })} className="w-full mt-1" />
        </div>
      </div>
    </div>
  );
}

// ─── Per-line style controls (full, same as global) ───────────────────────────
function PerLineStyleControls({ lineStyle, globalStyle, text, hasOverride, lbl, onChange, onReset }: {
  lineStyle: Partial<SubLineStyle>; globalStyle: StyleConfig;
  text: string; hasOverride: boolean; lbl: Lbl;
  onChange: (updates: Partial<SubLineStyle>) => void;
  onReset: () => void;
}) {
  const [localColorPicker, setLocalColorPicker] = useState<string | null>(null);

  const ef = (key: keyof SubLineStyle, fallback: unknown) => (key in lineStyle ? lineStyle[key] : fallback) as never;

  const colorFields: { key: keyof SubLineStyle; label: string; fallback: string }[] = [
    { key: "primary_color",   label: lbl.colorText,    fallback: globalStyle.primary_color   ?? "#fff" },
    { key: "secondary_color", label: lbl.colorKaraoke, fallback: globalStyle.secondary_color ?? "#ff0" },
    { key: "outline_color",   label: lbl.colorOutline, fallback: globalStyle.outline_color   ?? "#000" },
    { key: "shadow_color",    label: lbl.colorShadow,  fallback: globalStyle.shadow_color    ?? "#000" },
  ];

  const effectiveFont     = ef("font_family",  globalStyle.font_family  ?? "Noto Sans") as string;
  const effectiveSize     = ef("font_size",     globalStyle.font_size    ?? 52) as number;
  const effectiveOutline  = ef("outline_size",  globalStyle.outline_size ?? 2.5) as number;
  const effectiveShadow   = ef("shadow_size",   globalStyle.shadow_size  ?? 1.5) as number;
  const effectiveBold     = ef("bold",          globalStyle.bold         ?? true) as boolean;
  const effectiveItalic   = ef("italic",        globalStyle.italic       ?? false) as boolean;
  const effectiveAnim     = ef("animation",     globalStyle.animation    ?? "none") as string;
  const effectiveAlign    = ef("alignment",     globalStyle.alignment    ?? 2) as number;
  const effectiveMarginV  = ef("margin_v",      globalStyle.margin_v     ?? 40) as number;

  return (
    <div className="space-y-3">
      {/* Font + Size */}
      <div className="grid grid-cols-2 gap-2">
        <div className="space-y-1">
          <label className="text-[11px] text-white/50">{lbl.font}</label>
          <select value={effectiveFont} onChange={(e) => onChange({ font_family: e.target.value })}
            className="w-full bg-white/5 border border-white/20 rounded-lg px-2 py-1.5 text-xs text-white focus:outline-none focus:border-violet-500">
            {FONTS.map((f) => <option key={f} value={f} className="bg-gray-900">{f}</option>)}
          </select>
        </div>
        <div className="space-y-1">
          <label className="text-[11px] text-white/50">{lbl.size} ({effectiveSize}px)</label>
          <input type="range" min={20} max={96} step={2} value={effectiveSize}
            onChange={(e) => onChange({ font_size: +e.target.value })} className="w-full mt-2" />
        </div>
        <div className="space-y-1">
          <label className="text-[11px] text-white/50">{lbl.outline} ({effectiveOutline}px)</label>
          <input type="range" min={0} max={10} step={0.5} value={effectiveOutline}
            onChange={(e) => onChange({ outline_size: +e.target.value })} className="w-full mt-2" />
        </div>
        <div className="space-y-1">
          <label className="text-[11px] text-white/50">{lbl.shadow} ({effectiveShadow}px)</label>
          <input type="range" min={0} max={10} step={0.5} value={effectiveShadow}
            onChange={(e) => onChange({ shadow_size: +e.target.value })} className="w-full mt-2" />
        </div>
      </div>

      {/* B/I */}
      <div className="flex gap-1.5">
        {[
          { key: "bold"   as const, label: "B", active: effectiveBold },
          { key: "italic" as const, label: "I", active: effectiveItalic },
        ].map(({ key, label, active }) => (
          <button key={key} onClick={() => onChange({ [key]: !active })}
            className={`w-8 h-8 rounded-lg border text-sm transition ${active ? "border-violet-500 bg-violet-600 text-white" : "border-white/20 bg-white/5 text-white/50 hover:text-white"}`}>
            {label}
          </button>
        ))}
      </div>

      {/* Colors */}
      <div className="grid grid-cols-4 gap-1.5">
        {colorFields.map(({ key, label, fallback }) => {
          const color = (lineStyle[key] as string | undefined) ?? fallback;
          const pickerKey = `line-${key}`;
          return (
            <div key={key} className="relative">
              <button onClick={() => setLocalColorPicker(localColorPicker === pickerKey ? null : pickerKey)}
                className="w-full flex flex-col items-center gap-1 p-1.5 rounded-xl border border-white/10 hover:border-violet-400 transition bg-white/5">
                <span className="w-7 h-7 rounded-lg border border-white/20 block" style={{ background: color }} />
                <span className="text-[9px] text-white/50 text-center leading-none">{label}</span>
              </button>
              {localColorPicker === pickerKey && (
                <div className="absolute z-50 top-full mt-1 left-0">
                  <div className="p-2 bg-gray-900 border border-white/20 rounded-xl shadow-2xl">
                    <HexColorPicker color={color} onChange={(c) => onChange({ [key]: c })} />
                    <button onClick={() => setLocalColorPicker(null)} className="mt-2 w-full text-xs text-white/40 hover:text-white">{lbl.close}</button>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Animation */}
      <div className="space-y-1.5">
        <label className="text-[11px] text-white/50">{lbl.animation}</label>
        <div className="grid grid-cols-3 gap-1">
          {ANIMATIONS.map((a) => (
            <button key={a} onClick={() => onChange({ animation: a })}
              className={`py-1.5 rounded-lg text-xs capitalize transition ${effectiveAnim === a ? "bg-violet-600 text-white" : "bg-white/5 text-white/40 border border-white/10 hover:text-white"}`}>
              {a}
            </button>
          ))}
        </div>
      </div>

      {/* Position + Margin V */}
      <div className="flex items-start gap-4">
        <div className="space-y-1.5">
          <label className="text-[11px] text-white/50">{lbl.position}</label>
          <div className="grid grid-cols-3 gap-0.5 w-20">
            {ALIGNMENTS.map((a) => (
              <button key={a.val} onClick={() => onChange({ alignment: a.val })}
                className={`aspect-square rounded text-xs font-bold transition ${effectiveAlign === a.val ? "bg-violet-600 text-white" : "bg-white/10 text-white/50 hover:bg-white/20"}`}>
                {a.label}
              </button>
            ))}
          </div>
        </div>
        <div className="flex-1 space-y-1">
          <label className="text-[11px] text-white/50">{lbl.marginV} ({effectiveMarginV}px)</label>
          <input type="range" min={0} max={200} step={5} value={effectiveMarginV}
            onChange={(e) => onChange({ margin_v: +e.target.value })} className="w-full mt-1" />
        </div>
      </div>

      {/* Reset */}
      {hasOverride && (
        <button onClick={onReset}
          className="text-xs text-white/30 hover:text-red-400 transition flex items-center gap-1">
          <X size={10} /> {lbl.resetGlobal}
        </button>
      )}
    </div>
  );
}

// ─── Page entry point ─────────────────────────────────────────────────────────
export default function EditorPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 size={32} className="animate-spin text-violet-400" />
      </div>
    }>
      <EditorContent />
    </Suspense>
  );
}
