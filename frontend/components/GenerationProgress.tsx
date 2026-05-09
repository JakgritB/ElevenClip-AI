"use client";
import { useState, useEffect } from "react";
import {
  Download, Music, Film, Mic, Eye, Star, Scissors, Type,
  CheckCircle2, AlertCircle, Zap, Brain, LucideProps,
} from "lucide-react";

type LucideIcon = React.ComponentType<LucideProps>;

const STAGES: Record<string, { en: string; th: string; zh: string; Icon: LucideIcon }> = {
  download:  { en: "Download Video",    th: "ดาวน์โหลดวิดีโอ",    zh: "下载视频",    Icon: Download },
  audio:     { en: "Extract Audio",     th: "แยกเสียง",            zh: "提取音频",    Icon: Music },
  scenes:    { en: "Scene Detection",   th: "ตรวจจับฉาก",          zh: "场景检测",    Icon: Film },
  transcribe:{ en: "Transcribe",        th: "ถอดเสียง (Whisper)",  zh: "语音转录",    Icon: Mic },
  vision:    { en: "Vision Analysis",   th: "วิเคราะห์ด้วย AI",    zh: "视觉分析",    Icon: Eye },
  scoring:   { en: "Highlight Scoring", th: "คัดเลือกไฮไลท์",      zh: "精彩评分",    Icon: Star },
  cutting:   { en: "Cut Clips",         th: "ตัดคลิป",             zh: "剪切片段",    Icon: Scissors },
  subtitles: { en: "Generate Subtitles",th: "สร้างซับไตเติ้ล",     zh: "生成字幕",    Icon: Type },
  done:      { en: "Done!",             th: "เสร็จสิ้น!",          zh: "完成！",      Icon: CheckCircle2 },
  error:     { en: "Error",             th: "เกิดข้อผิดพลาด",       zh: "错误",        Icon: AlertCircle },
};

type Lang = "en" | "th" | "zh";

interface Props {
  stage: string;
  pct: number;
  message: string;
  uiLang?: Lang;
}

export default function GenerationProgress({ stage, pct, message, uiLang = "en" }: Props) {
  const info = STAGES[stage] ?? { en: stage, th: stage, zh: stage, Icon: Film };
  const Icon = info.Icon;
  const label = uiLang === "th" ? info.th : uiLang === "zh" ? info.zh : info.en;
  const isError = stage === "error";

  // Fake progress: slowly animate toward 4% when real pct is 0 (pipeline just started)
  const [fakePct, setFakePct] = useState(0);
  useEffect(() => {
    if (pct > 0 || isError || stage === "done") { setFakePct(0); return; }
    const id = setInterval(() => setFakePct((p) => Math.min(p + 0.3, 4)), 400);
    return () => clearInterval(id);
  }, [pct, isError, stage]);
  const displayPct = Math.max(pct, Math.round(fakePct * 10) / 10);

  const progressLabel = uiLang === "th" ? "ความคืบหน้า" : uiLang === "zh" ? "处理进度" : "Progress";

  return (
    <div className="space-y-4 py-2">
      {/* AMD badge */}
      <div className="flex items-center justify-center gap-2">
        <span className="px-3 py-1 bg-orange-500/20 border border-orange-500/40 rounded-full text-xs text-orange-300 font-medium flex items-center gap-1.5">
          <Zap size={12} /> AMD ROCm GPU Processing
        </span>
      </div>

      {/* Stage icon + label */}
      <div className="text-center">
        <div className="flex justify-center mb-2">
          <div className={`w-12 h-12 rounded-2xl flex items-center justify-center ${
            isError
              ? "bg-red-500/20"
              : stage === "done"
              ? "bg-green-500/20"
              : "bg-violet-500/20 animate-pulse"
          }`}>
            <Icon
              size={24}
              className={
                isError ? "text-red-400"
                : stage === "done" ? "text-green-400"
                : "text-violet-300"
              }
            />
          </div>
        </div>
        <h3 className="text-lg font-semibold text-white">{label}</h3>
        {message && <p className="text-sm text-white/50 mt-1">{message}</p>}
      </div>

      {/* Progress bar */}
      <div className="space-y-2">
        <div className="flex justify-between text-xs text-white/40">
          <span>{progressLabel}</span>
          <span>{displayPct}%</span>
        </div>
        <div className="w-full h-3 bg-white/10 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ${
              isError ? "bg-red-500"
              : displayPct >= 100 ? "bg-green-500"
              : "bg-gradient-to-r from-violet-500 via-fuchsia-500 to-pink-500"
            }`}
            style={{ width: `${displayPct}%` }}
          />
        </div>
      </div>

      {/* Stage grid */}
      <div className="grid grid-cols-4 gap-2">
        {Object.entries(STAGES)
          .filter(([k]) => k !== "error")
          .map(([key, val], i, arr) => {
            const stageKeys = arr.map(([k]) => k);
            const currentIdx = stageKeys.indexOf(stage);
            const done = i < currentIdx;
            const active = i === currentIdx;
            const StageIcon = val.Icon;
            const stageLabel = uiLang === "th" ? val.th : uiLang === "zh" ? val.zh : val.en;
            return (
              <div
                key={key}
                className={`text-center p-2 rounded-lg text-xs transition-all ${
                  done   ? "bg-green-500/20 text-green-300"
                  : active ? "bg-violet-500/30 text-violet-200 ring-1 ring-violet-500"
                  : "bg-white/5 text-white/30"
                }`}
              >
                <div className="flex justify-center mb-0.5">
                  <StageIcon size={14} />
                </div>
                <div className="truncate">{stageLabel.split(" ")[0]}</div>
              </div>
            );
          })}
      </div>

      {/* Multimodal info — compact single line */}
      {(stage === "vision" || stage === "transcribe") && (
        <div className="bg-blue-500/10 border border-blue-500/20 rounded-xl px-3 py-2 text-xs text-blue-200 flex items-center gap-2">
          <Brain size={12} className="shrink-0" />
          <span>
            {uiLang === "th" ? "Multimodal AI: Whisper ROCm · Qwen3-VL · librosa"
             : uiLang === "zh" ? "多模态 AI: Whisper ROCm · Qwen3-VL · librosa"
             : "Multimodal AI: Whisper ROCm · Qwen3-VL · librosa"}
          </span>
        </div>
      )}
    </div>
  );
}
