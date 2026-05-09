"use client";
import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import VideoUpload from "@/components/VideoUpload";
import ClipSettings from "@/components/ClipSettings";
import SubtitleDesigner from "@/components/SubtitleDesigner";
import GenerationProgress from "@/components/GenerationProgress";
import { startProcessing, connectProgressWS, type StyleConfig, type ProcessSettings } from "@/lib/api";
import { Scissors, Check, ChevronLeft, ArrowRight, Zap, Sparkles, PlayCircle } from "lucide-react";

const LANGS = [
  { code: "en", label: "English" },
  { code: "th", label: "ไทย" },
  { code: "zh", label: "中文" },
] as const;

const T = {
  en: {
    heroTitle: "AI Highlight Clipper",
    heroSub: "Livestream to TikTok · AMD MI300X · Vision + Audio + Text Multimodal",
    steps: ["Video", "Settings", "Subtitles"] as [string, string, string],
    addVideo: "Add Video",
    clipSettings: "Clip Settings",
    subtitleDesign: "Design Subtitles",
    back: "Back",
    next: "Next",
    generate: "Generate Clips!",
    generateHRE: "Generate with HRE",
    tryDemo: "Try Demo",
    demoHint: "Demo mode — works without backend",
    hackathon: "AMD Developer Hackathon 2026 · Track 3: Vision & Multimodal AI",
  },
  th: {
    heroTitle: "ตัดคลิปไฮไลท์ด้วย AI",
    heroSub: "จาก livestream สู่ TikTok · AMD MI300X · Vision + Audio + Text Multimodal",
    steps: ["วิดีโอ", "ตั้งค่า", "ซับ"] as [string, string, string],
    addVideo: "เพิ่มวิดีโอ",
    clipSettings: "ตั้งค่าคลิป",
    subtitleDesign: "ออกแบบซับไตเติ้ล",
    back: "ย้อนกลับ",
    next: "ถัดไป",
    generate: "สร้างคลิปเลย!",
    generateHRE: "สร้างด้วย HRE",
    tryDemo: "ลองดูตัวอย่าง",
    demoHint: "โหมด Demo — ไม่ต้องเชื่อม backend",
    hackathon: "AMD Developer Hackathon 2026 · Track 3: Vision & Multimodal AI",
  },
  zh: {
    heroTitle: "AI 精彩片段剪辑",
    heroSub: "直播到 TikTok · AMD MI300X · 视觉 + 音频 + 文本多模态",
    steps: ["视频", "设置", "字幕"] as [string, string, string],
    addVideo: "添加视频",
    clipSettings: "片段设置",
    subtitleDesign: "字幕设计",
    back: "返回",
    next: "下一步",
    generate: "生成片段！",
    generateHRE: "HRE 生成",
    tryDemo: "试用演示",
    demoHint: "演示模式 — 无需后端连接",
    hackathon: "AMD Developer Hackathon 2026 · Track 3: Vision & Multimodal AI",
  },
} as const;

type Lang = keyof typeof T;
type Step = 1 | 2 | 3 | "generating";

// Set NEXT_PUBLIC_DEMO_ENABLED=false in production to hide the demo button
const DEMO_ENABLED = process.env.NEXT_PUBLIC_DEMO_ENABLED !== "false";

const FONT_MAP: Record<string, string> = {
  thai: "Noto Sans Thai",
  chinese: "Noto Sans SC",
  japanese: "Noto Sans JP",
  korean: "Noto Sans KR",
  english: "Montserrat",
};

const DEMO_STAGES = [
  { stage: "download",  pct: 10, message: "Fetching sample video (yt-dlp)..." },
  { stage: "audio",     pct: 22, message: "Extracting audio track..." },
  { stage: "scenes",    pct: 35, message: "PySceneDetect — 24 scenes found" },
  { stage: "transcribe",pct: 50, message: "Whisper ROCm — transcribing 3m 42s..." },
  { stage: "vision",    pct: 65, message: "Qwen3-VL analyzing frames + transcript..." },
  { stage: "scoring",   pct: 80, message: "score = 0.4×vision + 0.35×audio + 0.25×text" },
  { stage: "cutting",   pct: 90, message: "Cutting 3 highlight clips via ffmpeg-amf..." },
  { stage: "subtitles", pct: 96, message: "Generating ASS subtitles (pysubs2)..." },
  { stage: "done",      pct: 100, message: "" },
];

export default function HomePage() {
  const router = useRouter();
  const [uiLang, setUiLang] = useState<Lang>("en");
  const t = T[uiLang];

  useEffect(() => {
    const saved = localStorage.getItem("elevnclip-lang") as Lang | null;
    if (saved && (["en", "th", "zh"] as string[]).includes(saved)) setUiLang(saved);
  }, []);

  const handleLangChange = (lang: Lang) => {
    setUiLang(lang);
    localStorage.setItem("elevnclip-lang", lang);
  };

  const [step, setStep] = useState<Step>(1);
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [channelDesc, setChannelDesc] = useState("");

  const [clipSettings, setClipSettings] = useState({
    clip_style: "funny",
    target_duration: 60,
    clip_count: 3,
    clip_language: "auto",
    subtitle_language: "english",
    mode: "normal" as "normal" | "hre",
  });

  const [styleConfig, setStyleConfig] = useState<StyleConfig>({
    font_family: "Montserrat",
    font_size: 64,
    primary_color: "#FFFFFF",
    secondary_color: "#FFFF00",
    outline_color: "#000000",
    shadow_color: "#000000",
    bold: true,
    italic: false,
    underline: false,
    outline_size: 3.0,
    shadow_size: 1.5,
    alignment: 2,
    margin_l: 20,
    margin_r: 20,
    margin_v: 250,
    display_mode: "word",
    animation: "pop",
    fade_in_ms: 200,
    fade_out_ms: 150,
  });

  const [progress, setProgress] = useState({ stage: "download", pct: 0, message: "" });
  const wsRef = useRef<WebSocket | null>(null);
  const demoTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const canProceedStep1 = !!videoFile;

  useEffect(() => {
    const font = FONT_MAP[clipSettings.subtitle_language] ?? "Noto Sans";
    setStyleConfig((c) => ({ ...c, font_family: font }));
  }, [clipSettings.subtitle_language]);

  useEffect(() => () => {
    wsRef.current?.close();
    if (demoTimerRef.current) clearInterval(demoTimerRef.current);
  }, []);

  const handleGenerate = async () => {
    if (!canProceedStep1) return;
    setStep("generating");
    try {
      const settings: ProcessSettings = {
        channel_description: channelDesc,
        ...clipSettings,
        style_config: clipSettings.mode === "hre" ? {} : { ...styleConfig, subtitle_language: clipSettings.subtitle_language },
      };
      const sessionId = await startProcessing(settings, videoFile ?? undefined);
      localStorage.setItem("elevnclip_session", sessionId);

      let wsAlive = false;
      const ws = connectProgressWS(sessionId, (data) => {
        wsAlive = true;
        setProgress(data);
        if (data.stage === "done") { ws.close(); router.push(`/editor?session=${sessionId}`); }
        if (data.stage === "error") ws.close();
      });
      wsRef.current = ws;

      // HTTP polling fallback — kicks in if WS doesn't deliver messages
      const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const poll = setInterval(async () => {
        try {
          const res = await fetch(`${API_BASE}/api/clips/${sessionId}`);
          const data = await res.json();
          const lp = data.last_progress;
          if (!wsAlive && lp) setProgress(lp);
          if (data.status === "done") {
            clearInterval(poll);
            if (!wsAlive) router.push(`/editor?session=${sessionId}`);
          }
          if (data.status === "error") clearInterval(poll);
        } catch { /* ignore */ }
      }, 3000);
      // Stop polling after 10 min
      setTimeout(() => clearInterval(poll), 600_000);
    } catch (e: unknown) {
      setProgress({ stage: "error", pct: 0, message: e instanceof Error ? e.message : "Error" });
    }
  };

  const handleDemo = async () => {
    setStep("generating");
    try {
      const settings: ProcessSettings = {
        use_demo_video: true,
        channel_description: "Gaming and reaction channel with funny moments",
        clip_style: "funny",
        target_duration: 60,
        clip_count: 3,
        clip_language: "auto",
        subtitle_language: "english",
        mode: "hre",
        style_config: {},
      };
      const sessionId = await startProcessing(settings);
      localStorage.setItem("elevnclip_session", sessionId);

      const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const ws = connectProgressWS(sessionId, (data) => {
        setProgress(data);
        if (data.stage === "done") { ws.close(); router.push(`/editor?session=${sessionId}`); }
        if (data.stage === "error") ws.close();
      });
      wsRef.current = ws;

      const poll = setInterval(async () => {
        try {
          const res = await fetch(`${API_BASE}/api/clips/${sessionId}`);
          const data = await res.json();
          if (data.last_progress) setProgress(data.last_progress);
          if (data.status === "done") { clearInterval(poll); router.push(`/editor?session=${sessionId}`); }
          if (data.status === "error") clearInterval(poll);
        } catch { /* ignore */ }
      }, 3000);
      setTimeout(() => clearInterval(poll), 600_000);
    } catch {
      // Fallback to fake demo animation if server unavailable
      let i = 0;
      demoTimerRef.current = setInterval(() => {
        if (i < DEMO_STAGES.length) {
          setProgress(DEMO_STAGES[i]);
          if (DEMO_STAGES[i].stage === "done") {
            clearInterval(demoTimerRef.current!);
            setTimeout(() => router.push("/editor?session=demo"), 600);
          }
          i++;
        }
      }, 900);
    }
  };

  return (
    <div className="h-screen flex flex-col overflow-hidden">
      {/* Navbar */}
      <nav className="border-b border-white/10 px-6 py-3 flex items-center justify-between bg-black/30 backdrop-blur shrink-0 z-40">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-gradient-to-br from-violet-500 to-pink-500 rounded-lg flex items-center justify-center">
            <Scissors size={16} className="text-white" />
          </div>
          <div>
            <span className="font-bold">ElevenClip AI</span>
            <span className="ml-2 text-xs text-white/30">AMD ROCm · Qwen3-VL · Whisper</span>
          </div>
        </div>
        <div className="flex gap-1">
          {LANGS.map((l) => (
            <button
              key={l.code}
              onClick={() => handleLangChange(l.code as Lang)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                uiLang === l.code ? "bg-violet-600 text-white" : "text-white/40 hover:text-white hover:bg-white/10"
              }`}
            >
              {l.label}
            </button>
          ))}
        </div>
      </nav>

      {/* Hero */}
      <div className="text-center py-3 px-4 shrink-0">
        <h1 className="text-3xl font-bold bg-gradient-to-r from-violet-400 via-pink-400 to-orange-400 bg-clip-text text-transparent">
          {t.heroTitle}
        </h1>
        <p className="text-white/40 mt-1 text-xs">{t.heroSub}</p>
      </div>

      {/* Main card */}
      <div className="flex-1 flex flex-col items-center px-4 pb-3 min-h-0 overflow-hidden">
        <div className="w-full max-w-2xl flex flex-col flex-1 min-h-0">
          {/* Step indicator */}
          {step !== "generating" && (
            <div className="flex items-center gap-2 mb-3 shrink-0">
              {([1, 2, 3] as const).map((s) => (
                <div key={s} className="flex items-center gap-2 flex-1">
                  <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold transition-all ${
                    step === s
                      ? "bg-violet-600 text-white ring-2 ring-violet-400"
                      : (step as number) > s
                      ? "bg-green-500 text-white"
                      : "bg-white/10 text-white/30"
                  }`}>
                    {(step as number) > s ? <Check size={14} /> : s}
                  </div>
                  <span className={`text-xs font-medium ${step === s ? "text-white" : "text-white/30"}`}>
                    {t.steps[s - 1]}
                  </span>
                  {s < 3 && <div className="flex-1 h-px bg-white/10" />}
                </div>
              ))}
            </div>
          )}

          <div className="bg-white/5 border border-white/10 rounded-2xl p-5 backdrop-blur-sm flex-1 min-h-0 overflow-y-auto flex flex-col">
            {step === 1 && (
              <>
                <h2 className="text-lg font-semibold mb-4">{t.addVideo}</h2>
                <VideoUpload
                  onFileSelect={(f) => setVideoFile(f)}
                  onChannelDesc={setChannelDesc}
                  channelDesc={channelDesc}
                  uiLang={uiLang}
                />
              </>
            )}

            {step === 2 && (
              <>
                <h2 className="text-lg font-semibold mb-4">{t.clipSettings}</h2>
                <ClipSettings
                  settings={clipSettings}
                  onChange={(s) => setClipSettings((c) => ({ ...c, ...s }))}
                  uiLang={uiLang}
                />
              </>
            )}

            {step === 3 && clipSettings.mode === "normal" && (
              <>
                <h2 className="text-lg font-semibold mb-4">{t.subtitleDesign}</h2>
                <SubtitleDesigner
                  config={styleConfig}
                  onChange={(c) => setStyleConfig((p) => ({ ...p, ...c }))}
                  subtitleLanguage={clipSettings.subtitle_language}
                  uiLang={uiLang}
                />
              </>
            )}

            {step === "generating" && <GenerationProgress {...progress} uiLang={uiLang} />}

            {/* Navigation */}
            {step !== "generating" && (
              <div className="flex gap-3 mt-auto pt-4 border-t border-white/10">
                {(step as number) > 1 && (
                  <button
                    onClick={() => setStep((s) => ((s as number) - 1) as Step)}
                    className="px-5 py-3 rounded-xl border border-white/20 text-white/70 hover:text-white transition font-medium flex items-center gap-2"
                  >
                    <ChevronLeft size={16} /> {t.back}
                  </button>
                )}

                {step === 1 && (
                  <div className="flex-1 flex gap-2">
                    {DEMO_ENABLED && (
                      <button
                        onClick={handleDemo}
                        className="px-4 py-3 rounded-xl border border-violet-500/50 text-violet-300 hover:bg-violet-600/20 transition font-medium flex items-center gap-2 text-sm whitespace-nowrap"
                      >
                        <PlayCircle size={16} /> {t.tryDemo}
                      </button>
                    )}
                    <button
                      onClick={() => setStep(2)}
                      disabled={!canProceedStep1}
                      className="flex-1 py-3 bg-violet-600 hover:bg-violet-700 disabled:opacity-40 rounded-xl text-white font-semibold transition flex items-center justify-center gap-2"
                    >
                      {t.next} <ArrowRight size={16} />
                    </button>
                  </div>
                )}

                {step === 2 && (
                  <button
                    onClick={() => clipSettings.mode === "hre" ? handleGenerate() : setStep(3)}
                    className="flex-1 py-3 bg-violet-600 hover:bg-violet-700 rounded-xl text-white font-semibold transition flex items-center justify-center gap-2"
                  >
                    {clipSettings.mode === "hre"
                      ? <><Zap size={16} /> {t.generateHRE}</>
                      : <>{t.next} <ArrowRight size={16} /></>}
                  </button>
                )}

                {step === 3 && (
                  <button
                    onClick={handleGenerate}
                    disabled={!canProceedStep1}
                    className="flex-1 py-3 bg-gradient-to-r from-violet-600 to-pink-600 hover:from-violet-700 hover:to-pink-700 disabled:opacity-40 rounded-xl text-white font-bold transition shadow-lg shadow-violet-500/25 flex items-center justify-center gap-2"
                  >
                    <Sparkles size={16} /> {t.generate}
                  </button>
                )}
              </div>
            )}
          </div>

          {step === 1 && DEMO_ENABLED && (
            <p className="text-center text-xs text-white/20 mt-2 shrink-0">{t.demoHint}</p>
          )}

          <div className="flex items-center justify-center mt-2 text-xs text-white/20 shrink-0">
            <span>{t.hackathon}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
