"use client";
import { useState, useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { Upload, Link, Loader2, CheckCircle, Film } from "lucide-react";
import { getVideoInfo } from "@/lib/api";

const L = {
  en: {
    upload: "Upload File",
    replace: "Click or drag a new file to replace",
    drag: "Drag video here, or click to select",
    fetch: "Fetch",
    fetchError: "Could not fetch video",
    channelLabel: "Channel Description",
    channelOpt: "(optional — helps AI analyze better)",
    channelPlaceholder: "e.g. English gaming channel focused on funny reactions and horror games",
  },
  th: {
    upload: "อัปโหลดไฟล์",
    replace: "คลิกหรือลากไฟล์ใหม่เพื่อเปลี่ยน",
    drag: "ลากวิดีโอมาวางที่นี่ หรือคลิกเพื่อเลือก",
    fetch: "ดึงข้อมูล",
    fetchError: "ดึงข้อมูลไม่ได้",
    channelLabel: "คำอธิบายช่อง",
    channelOpt: "(ไม่บังคับ — ช่วย AI วิเคราะห์ได้ดีขึ้น)",
    channelPlaceholder: "เช่น: ช่องเกมมิ่งภาษาไทย เน้นตลก reaction และ horror game",
  },
  zh: {
    upload: "上传文件",
    replace: "点击或拖入新文件以替换",
    drag: "将视频拖到此处，或点击选择",
    fetch: "获取",
    fetchError: "无法获取视频信息",
    channelLabel: "频道描述",
    channelOpt: "（可选 — 帮助 AI 更好地分析）",
    channelPlaceholder: "例：中文游戏频道，专注搞笑反应和恐怖游戏",
  },
} as const;

type Lang = keyof typeof L;

interface Props {
  onFileSelect: (file: File) => void;
  onUrlSelect: (url: string, info?: Record<string, unknown>) => void;
  onChannelDesc: (desc: string) => void;
  channelDesc: string;
  uiLang?: Lang;
}

export default function VideoUpload({ onFileSelect, onUrlSelect, onChannelDesc, channelDesc, uiLang = "en" }: Props) {
  const lbl = L[uiLang];
  const [tab, setTab] = useState<"upload" | "youtube">("upload");
  const [url, setUrl] = useState("");
  const [videoInfo, setVideoInfo] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [fileName, setFileName] = useState("");

  const onDrop = useCallback((files: File[]) => {
    if (files[0]) {
      setFileName(files[0].name);
      onFileSelect(files[0]);
    }
  }, [onFileSelect]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "video/*": [".mp4", ".mov", ".avi", ".mkv", ".webm"] },
    maxFiles: 1,
  });

  const fetchInfo = async () => {
    if (!url.trim()) return;
    setLoading(true);
    setError("");
    try {
      const info = await getVideoInfo(url);
      setVideoInfo(info);
      onUrlSelect(url, info);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : lbl.fetchError);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Tab switcher */}
      <div className="flex rounded-xl overflow-hidden border border-white/10 bg-white/5">
        {(["upload", "youtube"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`flex-1 py-3 text-sm font-medium transition-all flex items-center justify-center gap-2 ${
              tab === t
                ? "bg-violet-600 text-white"
                : "text-white/60 hover:text-white hover:bg-white/5"
            }`}
          >
            {t === "upload" ? <Upload size={16} /> : <Link size={16} />}
            {t === "upload" ? lbl.upload : "YouTube URL"}
          </button>
        ))}
      </div>

      {/* Upload tab */}
      {tab === "upload" && (
        <div
          {...getRootProps()}
          className={`border-2 border-dashed rounded-2xl p-5 text-center cursor-pointer transition-all ${
            isDragActive
              ? "border-violet-500 bg-violet-500/10"
              : "border-white/20 hover:border-violet-400 hover:bg-white/5"
          }`}
        >
          <input {...getInputProps()} />
          {fileName ? (
            <div className="flex flex-col items-center gap-2 text-green-400">
              <CheckCircle size={28} />
              <p className="font-medium">{fileName}</p>
              <p className="text-sm text-white/50">{lbl.replace}</p>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-2 text-white/50">
              <Film size={28} />
              <p className="font-medium text-white/70">{lbl.drag}</p>
              <p className="text-sm">MP4, MOV, AVI, MKV, WebM</p>
            </div>
          )}
        </div>
      )}

      {/* YouTube tab */}
      {tab === "youtube" && (
        <div className="space-y-3">
          <div className="flex gap-2">
            <input
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && fetchInfo()}
              placeholder="https://youtube.com/watch?v=..."
              className="flex-1 bg-white/5 border border-white/20 rounded-xl px-4 py-3 text-white placeholder-white/30 focus:outline-none focus:border-violet-500 transition"
            />
            <button
              onClick={fetchInfo}
              disabled={loading || !url}
              className="px-4 py-3 bg-violet-600 hover:bg-violet-700 disabled:opacity-40 rounded-xl text-white font-medium transition flex items-center gap-2"
            >
              {loading ? <Loader2 size={16} className="animate-spin" /> : <Link size={16} />}
              {lbl.fetch}
            </button>
          </div>
          {error && <p className="text-red-400 text-sm">{error}</p>}
          {videoInfo && (
            <div className="bg-white/5 border border-white/10 rounded-xl p-4 flex gap-4">
              {videoInfo.thumbnail ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={String(videoInfo.thumbnail)} alt="thumb" className="w-24 h-16 object-cover rounded-lg" />
              ) : null}
              <div className="flex-1 min-w-0">
                <p className="font-medium text-white truncate">{String(videoInfo.title ?? "")}</p>
                <p className="text-sm text-white/50">{String(videoInfo.channel ?? "")}</p>
                <p className="text-sm text-violet-300">{formatDuration(Number(videoInfo.duration ?? 0))}</p>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Channel description */}
      <div className="space-y-2">
        <label className="text-sm font-medium text-white/70">
          {lbl.channelLabel} <span className="text-white/30">{lbl.channelOpt}</span>
        </label>
        <textarea
          value={channelDesc}
          onChange={(e) => onChannelDesc(e.target.value)}
          placeholder={lbl.channelPlaceholder}
          rows={1}
          className="w-full bg-white/5 border border-white/20 rounded-xl px-4 py-3 text-white placeholder-white/30 focus:outline-none focus:border-violet-500 transition resize-none"
        />
      </div>
    </div>
  );
}

function formatDuration(sec: number): string {
  if (!sec) return "";
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = sec % 60;
  return h > 0 ? `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}` : `${m}:${String(s).padStart(2, "0")}`;
}
