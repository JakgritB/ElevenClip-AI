"use client";
import { useState, useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { Upload, CheckCircle, Film } from "lucide-react";

const L = {
  en: {
    upload: "Upload File",
    replace: "Click or drag a new file to replace",
    drag: "Drag video here, or click to select",
    channelLabel: "Channel Description",
    channelOpt: "(optional — helps AI analyze better)",
    channelPlaceholder: "e.g. English gaming channel focused on funny reactions and horror games",
    accessLabel: "Demo Access Code",
    accessOpt: "(required for GPU generation when enabled)",
    accessPlaceholder: "Enter the code shared by the team",
  },
  th: {
    upload: "อัปโหลดไฟล์",
    replace: "คลิกหรือลากไฟล์ใหม่เพื่อเปลี่ยน",
    drag: "ลากวิดีโอมาวางที่นี่ หรือคลิกเพื่อเลือก",
    channelLabel: "คำอธิบายช่อง",
    channelOpt: "(ไม่บังคับ — ช่วย AI วิเคราะห์ได้ดีขึ้น)",
    channelPlaceholder: "เช่น: ช่องเกมมิ่งภาษาไทย เน้นตลก reaction และ horror game",
    accessLabel: "รหัสเข้าใช้เดโม",
    accessOpt: "(จำเป็นเมื่อเปิดการป้องกัน GPU)",
    accessPlaceholder: "ใส่รหัสที่ทีมแชร์ให้",
  },
  zh: {
    upload: "上传文件",
    replace: "点击或拖入新文件以替换",
    drag: "将视频拖到此处，或点击选择",
    channelLabel: "频道描述",
    channelOpt: "（可选 — 帮助 AI 更好地分析）",
    channelPlaceholder: "例：中文游戏频道，专注搞笑反应和恐怖游戏",
    accessLabel: "演示访问码",
    accessOpt: "（启用 GPU 保护时需要）",
    accessPlaceholder: "输入团队分享的访问码",
  },
} as const;

type Lang = keyof typeof L;

interface Props {
  onFileSelect: (file: File) => void;
  onChannelDesc: (desc: string) => void;
  channelDesc: string;
  accessCode: string;
  onAccessCode: (code: string) => void;
  uiLang?: Lang;
}

export default function VideoUpload({
  onFileSelect,
  onChannelDesc,
  channelDesc,
  accessCode,
  onAccessCode,
  uiLang = "en",
}: Props) {
  const lbl = L[uiLang];
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

  return (
    <div className="space-y-4">
      {/* Drop zone */}
      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-2xl p-8 text-center cursor-pointer transition-all ${
          isDragActive
            ? "border-violet-500 bg-violet-500/10"
            : "border-white/20 hover:border-violet-400 hover:bg-white/5"
        }`}
      >
        <input {...getInputProps()} />
        {fileName ? (
          <div className="flex flex-col items-center gap-2 text-green-400">
            <CheckCircle size={32} />
            <p className="font-medium">{fileName}</p>
            <p className="text-sm text-white/50">{lbl.replace}</p>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-3 text-white/50">
            <Upload size={32} />
            <p className="font-medium text-white/70 text-base">{lbl.drag}</p>
            <p className="text-sm">MP4, MOV, AVI, MKV, WebM</p>
          </div>
        )}
      </div>

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

      {/* Access code */}
      <div className="space-y-2">
        <label className="text-sm font-medium text-white/70">
          {lbl.accessLabel} <span className="text-white/30">{lbl.accessOpt}</span>
        </label>
        <input
          type="password"
          value={accessCode}
          onChange={(e) => onAccessCode(e.target.value)}
          placeholder={lbl.accessPlaceholder}
          className="w-full bg-white/5 border border-white/20 rounded-xl px-4 py-3 text-white placeholder-white/30 focus:outline-none focus:border-violet-500 transition"
        />
      </div>
    </div>
  );
}
