"use client";
import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import VideoUpload from "@/components/VideoUpload";
import ClipSettings from "@/components/ClipSettings";
import SubtitleDesigner from "@/components/SubtitleDesigner";
import GenerationProgress from "@/components/GenerationProgress";
import { startProcessing, connectProgressWS, type StyleConfig, type ProcessSettings } from "@/lib/api";

const LANGS = [
  { code: "th", label: "ไทย" },
  { code: "en", label: "English" },
  { code: "zh", label: "中文" },
];

type Step = 1 | 2 | 3 | "generating";

const FONT_MAP: Record<string, string> = {
  thai: "Noto Sans Thai",
  chinese: "Noto Sans SC",
  japanese: "Noto Sans JP",
  korean: "Noto Sans KR",
  english: "Montserrat",
};

export default function HomePage() {
  const router = useRouter();
  const [uiLang, setUiLang] = useState("th");
  const [step, setStep] = useState<Step>(1);

  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [youtubeUrl, setYoutubeUrl] = useState("");
  const [channelDesc, setChannelDesc] = useState("");

  const [clipSettings, setClipSettings] = useState({
    clip_style: "funny",
    target_duration: 60,
    clip_count: 3,
    clip_language: "auto",
    subtitle_language: "thai",
    mode: "normal" as "normal" | "hre",
  });

  const [styleConfig, setStyleConfig] = useState<StyleConfig>({
    font_family: "Noto Sans Thai",
    font_size: 52,
    primary_color: "#FFFFFF",
    secondary_color: "#FFFF00",
    outline_color: "#000000",
    shadow_color: "#000000",
    bold: true,
    italic: false,
    underline: false,
    outline_size: 2.5,
    shadow_size: 1.5,
    alignment: 2,
    margin_l: 20,
    margin_r: 20,
    margin_v: 40,
    display_mode: "word",
    animation: "pop",
    fade_in_ms: 200,
    fade_out_ms: 150,
  });

  const [progress, setProgress] = useState({ stage: "download", pct: 0, message: "" });
  const wsRef = useRef<WebSocket | null>(null);

  const canProceedStep1 = !!(videoFile || youtubeUrl);

  useEffect(() => {
    const font = FONT_MAP[clipSettings.subtitle_language] ?? "Noto Sans";
    setStyleConfig((c) => ({ ...c, font_family: font }));
  }, [clipSettings.subtitle_language]);

  useEffect(() => () => wsRef.current?.close(), []);

  const handleGenerate = async () => {
    if (!canProceedStep1) return;
    setStep("generating");
    try {
      const settings: ProcessSettings = {
        youtube_url: youtubeUrl || undefined,
        channel_description: channelDesc,
        ...clipSettings,
        style_config: clipSettings.mode === "hre" ? {} : { ...styleConfig, subtitle_language: clipSettings.subtitle_language },
      };
      const sessionId = await startProcessing(settings, videoFile ?? undefined);
      localStorage.setItem("elevnclip_session", sessionId);
      const ws = connectProgressWS(sessionId, (data) => {
        setProgress(data);
        if (data.stage === "done") { ws.close(); router.push(`/editor?session=${sessionId}`); }
        if (data.stage === "error") ws.close();
      });
      wsRef.current = ws;
    } catch (e: unknown) {
      setProgress({ stage: "error", pct: 0, message: e instanceof Error ? e.message : "เกิดข้อผิดพลาด" });
    }
  };

  return (
    <div className="min-h-screen flex flex-col">
      {/* Navbar */}
      <nav className="border-b border-white/10 px-6 py-4 flex items-center justify-between bg-black/30 backdrop-blur sticky top-0 z-40">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-gradient-to-br from-violet-500 to-pink-500 rounded-lg flex items-center justify-center text-sm">✂️</div>
          <div>
            <span className="font-bold">ElevenClip AI</span>
            <span className="ml-2 text-xs text-white/30">AMD ROCm · Qwen3-VL · Whisper</span>
          </div>
        </div>
        <div className="flex gap-1">
          {LANGS.map((l) => (
            <button key={l.code} onClick={() => setUiLang(l.code)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${uiLang === l.code ? "bg-violet-600 text-white" : "text-white/40 hover:text-white hover:bg-white/10"}`}>
              {l.label}
            </button>
          ))}
        </div>
      </nav>

      {/* Hero */}
      <div className="text-center py-10 px-4">
        <h1 className="text-4xl font-bold bg-gradient-to-r from-violet-400 via-pink-400 to-orange-400 bg-clip-text text-transparent">
          ตัดคลิปไฮไลท์ด้วย AI
        </h1>
        <p className="text-white/50 mt-2 text-sm">จาก livestream สู่ TikTok · AMD MI300X · Vision + Audio + Text Multimodal</p>
      </div>

      {/* Main card */}
      <div className="flex-1 flex items-start justify-center px-4 pb-16">
        <div className="w-full max-w-2xl">
          {/* Step indicator */}
          {step !== "generating" && (
            <div className="flex items-center gap-2 mb-6">
              {[1, 2, 3].map((s) => (
                <div key={s} className="flex items-center gap-2 flex-1">
                  <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold transition-all ${
                    step === s ? "bg-violet-600 text-white ring-2 ring-violet-400"
                    : (step as number) > s ? "bg-green-500 text-white"
                    : "bg-white/10 text-white/30"}`}>
                    {(step as number) > s ? "✓" : s}
                  </div>
                  <span className={`text-xs font-medium ${step === s ? "text-white" : "text-white/30"}`}>
                    {s === 1 ? "วิดีโอ" : s === 2 ? "ตั้งค่า" : "ซับ"}
                  </span>
                  {s < 3 && <div className="flex-1 h-px bg-white/10" />}
                </div>
              ))}
            </div>
          )}

          <div className="bg-white/5 border border-white/10 rounded-2xl p-6 backdrop-blur-sm">
            {step === 1 && (
              <>
                <h2 className="text-lg font-semibold mb-4">เพิ่มวิดีโอ</h2>
                <VideoUpload
                  onFileSelect={(f) => { setVideoFile(f); setYoutubeUrl(""); }}
                  onUrlSelect={(u) => { setYoutubeUrl(u); setVideoFile(null); }}
                  onChannelDesc={setChannelDesc}
                  channelDesc={channelDesc}
                />
              </>
            )}

            {step === 2 && (
              <>
                <h2 className="text-lg font-semibold mb-4">ตั้งค่าคลิป</h2>
                <ClipSettings settings={clipSettings} onChange={(s) => setClipSettings((c) => ({ ...c, ...s }))} />
              </>
            )}

            {step === 3 && clipSettings.mode === "normal" && (
              <>
                <h2 className="text-lg font-semibold mb-4">ออกแบบซับไตเติ้ล</h2>
                <SubtitleDesigner
                  config={styleConfig}
                  onChange={(c) => setStyleConfig((p) => ({ ...p, ...c }))}
                  subtitleLanguage={clipSettings.subtitle_language}
                />
              </>
            )}

            {step === "generating" && <GenerationProgress {...progress} />}

            {/* Navigation */}
            {step !== "generating" && (
              <div className="flex gap-3 mt-6 pt-6 border-t border-white/10">
                {(step as number) > 1 && (
                  <button onClick={() => setStep((s) => ((s as number) - 1) as Step)}
                    className="px-5 py-3 rounded-xl border border-white/20 text-white/70 hover:text-white transition font-medium">
                    ← ย้อนกลับ
                  </button>
                )}

                {step === 1 && (
                  <button onClick={() => setStep(2)} disabled={!canProceedStep1}
                    className="flex-1 py-3 bg-violet-600 hover:bg-violet-700 disabled:opacity-40 rounded-xl text-white font-semibold transition">
                    ถัดไป →
                  </button>
                )}

                {step === 2 && (
                  <button onClick={() => clipSettings.mode === "hre" ? handleGenerate() : setStep(3)}
                    className="flex-1 py-3 bg-violet-600 hover:bg-violet-700 rounded-xl text-white font-semibold transition">
                    {clipSettings.mode === "hre" ? "⚡ สร้างคลิป" : "ถัดไป →"}
                  </button>
                )}

                {step === 3 && (
                  <button onClick={handleGenerate} disabled={!canProceedStep1}
                    className="flex-1 py-3 bg-gradient-to-r from-violet-600 to-pink-600 hover:from-violet-700 hover:to-pink-700 disabled:opacity-40 rounded-xl text-white font-bold transition shadow-lg shadow-violet-500/25">
                    ✨ สร้างคลิปเลย!
                  </button>
                )}
              </div>
            )}
          </div>

          <div className="flex items-center justify-center gap-3 mt-6 text-xs text-white/30">
            <span>AMD Developer Hackathon 2026</span>
            <span>·</span>
            <span>Track 3: Vision & Multimodal AI</span>
          </div>
        </div>
      </div>
    </div>
  );
}
