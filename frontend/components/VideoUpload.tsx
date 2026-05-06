"use client";
import { useState, useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { Upload, Link, Loader2, CheckCircle, Film } from "lucide-react";
import { getVideoInfo } from "@/lib/api";

interface Props {
  onFileSelect: (file: File) => void;
  onUrlSelect: (url: string, info?: Record<string, unknown>) => void;
  onChannelDesc: (desc: string) => void;
  channelDesc: string;
}

export default function VideoUpload({ onFileSelect, onUrlSelect, onChannelDesc, channelDesc }: Props) {
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
      setError(e instanceof Error ? e.message : "ดึงข้อมูลไม่ได้");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
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
            {t === "upload" ? "อัปโหลดไฟล์" : "YouTube URL"}
          </button>
        ))}
      </div>

      {/* Upload tab */}
      {tab === "upload" && (
        <div
          {...getRootProps()}
          className={`border-2 border-dashed rounded-2xl p-10 text-center cursor-pointer transition-all ${
            isDragActive
              ? "border-violet-500 bg-violet-500/10"
              : "border-white/20 hover:border-violet-400 hover:bg-white/5"
          }`}
        >
          <input {...getInputProps()} />
          {fileName ? (
            <div className="flex flex-col items-center gap-3 text-green-400">
              <CheckCircle size={40} />
              <p className="font-medium">{fileName}</p>
              <p className="text-sm text-white/50">คลิกหรือลากไฟล์ใหม่เพื่อเปลี่ยน</p>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-3 text-white/50">
              <Film size={40} />
              <p className="font-medium text-white/70">ลากวิดีโอมาวางที่นี่ หรือคลิกเพื่อเลือก</p>
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
              ดึงข้อมูล
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
          คำอธิบายช่อง <span className="text-white/30">(ไม่บังคับ — ช่วย AI วิเคราะห์ได้ดีขึ้น)</span>
        </label>
        <textarea
          value={channelDesc}
          onChange={(e) => onChannelDesc(e.target.value)}
          placeholder="เช่น: ช่องเกมมิ่งภาษาไทย เน้นตลก reaction และ horror game"
          rows={2}
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
