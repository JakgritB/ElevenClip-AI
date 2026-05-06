"use client";

const STAGES: Record<string, { label: string; icon: string }> = {
  download:  { label: "ดาวน์โหลดวิดีโอ",    icon: "⬇️" },
  audio:     { label: "แยกเสียง",            icon: "🎵" },
  scenes:    { label: "ตรวจจับฉาก",          icon: "🎬" },
  transcribe:{ label: "ถอดเสียง (Whisper)",  icon: "🎙️" },
  vision:    { label: "วิเคราะห์ด้วย AI",    icon: "👁️" },
  scoring:   { label: "คัดเลือกไฮไลท์",     icon: "⭐" },
  cutting:   { label: "ตัดคลิป",             icon: "✂️" },
  subtitles: { label: "สร้างซับไตเติ้ล",    icon: "📝" },
  done:      { label: "เสร็จสิ้น!",          icon: "✅" },
  error:     { label: "เกิดข้อผิดพลาด",      icon: "❌" },
};

interface Props {
  stage: string;
  pct: number;
  message: string;
}

export default function GenerationProgress({ stage, pct, message }: Props) {
  const info = STAGES[stage] ?? { label: stage, icon: "⚙️" };
  const isError = stage === "error";

  return (
    <div className="space-y-6 py-4">
      {/* AMD GPU badge */}
      <div className="flex items-center justify-center gap-2">
        <span className="px-3 py-1 bg-orange-500/20 border border-orange-500/40 rounded-full text-xs text-orange-300 font-medium">
          ⚡ AMD ROCm GPU Processing
        </span>
      </div>

      {/* Stage icon + label */}
      <div className="text-center">
        <div className="text-5xl mb-3">{info.icon}</div>
        <h3 className="text-lg font-semibold text-white">{info.label}</h3>
        {message && <p className="text-sm text-white/50 mt-1">{message}</p>}
      </div>

      {/* Progress bar */}
      <div className="space-y-2">
        <div className="flex justify-between text-xs text-white/40">
          <span>ความคืบหน้า</span>
          <span>{pct}%</span>
        </div>
        <div className="w-full h-3 bg-white/10 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ${
              isError
                ? "bg-red-500"
                : pct >= 100
                ? "bg-green-500"
                : "bg-gradient-to-r from-violet-500 via-fuchsia-500 to-pink-500"
            }`}
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>

      {/* Stage steps */}
      <div className="grid grid-cols-4 gap-2">
        {Object.entries(STAGES)
          .filter(([k]) => k !== "error")
          .map(([key, val], i, arr) => {
            const stageKeys = arr.map(([k]) => k);
            const currentIdx = stageKeys.indexOf(stage);
            const thisIdx = i;
            const done = thisIdx < currentIdx;
            const active = thisIdx === currentIdx;
            return (
              <div
                key={key}
                className={`text-center p-2 rounded-lg text-xs transition-all ${
                  done
                    ? "bg-green-500/20 text-green-300"
                    : active
                    ? "bg-violet-500/30 text-violet-200 ring-1 ring-violet-500"
                    : "bg-white/5 text-white/30"
                }`}
              >
                <div className="text-base">{val.icon}</div>
                <div className="truncate mt-0.5">{val.label.split(" ")[0]}</div>
              </div>
            );
          })}
      </div>

      {/* Multimodal info */}
      {(stage === "vision" || stage === "transcribe") && (
        <div className="bg-blue-500/10 border border-blue-500/20 rounded-xl p-3 text-xs text-blue-200 space-y-1">
          <div className="font-medium">🧠 Multimodal AI กำลังทำงาน</div>
          <div>• Whisper ROCm — ถอดเสียงแบบ word-level timestamps</div>
          <div>• Qwen3-VL — วิเคราะห์ frame + transcript พร้อมกัน</div>
          <div>• librosa — วัดพลังงานเสียงต่อฉาก</div>
        </div>
      )}
    </div>
  );
}
