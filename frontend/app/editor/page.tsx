"use client";
import { useEffect, useState, useRef, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { HexColorPicker } from "react-colorful";
import { getClips, patchSubtitle, patchGlobalStyle, renderClip, type ClipResult, type StyleConfig } from "@/lib/api";
import { Download, RotateCcw, ChevronDown, ChevronUp, Loader2 } from "lucide-react";

const FONTS = ["Noto Sans Thai", "Noto Sans SC", "Noto Sans", "Impact", "Montserrat", "Oswald", "Anton"];
const ANIMATIONS = ["none", "fade", "karaoke", "pop", "typewriter", "bounce"];
const ALIGNMENTS = [
  { val: 7, label: "↖" }, { val: 8, label: "↑" }, { val: 9, label: "↗" },
  { val: 4, label: "←" }, { val: 5, label: "·" }, { val: 6, label: "→" },
  { val: 1, label: "↙" }, { val: 2, label: "↓" }, { val: 3, label: "↘" },
];

function EditorContent() {
  const params = useSearchParams();
  const router = useRouter();
  const sessionId = params.get("session") ?? "";

  const [clips, setClips] = useState<ClipResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [activeClip, setActiveClip] = useState(0);
  const [rendering, setRendering] = useState<Record<number, boolean>>({});
  const [downloadUrls, setDownloadUrls] = useState<Record<number, string>>({});

  // Per-clip trim offsets
  const [trimStart, setTrimStart] = useState<Record<number, number>>({});
  const [trimEnd, setTrimEnd] = useState<Record<number, number>>({});

  // Global style state for editor
  const [globalStyle, setGlobalStyle] = useState<StyleConfig>({
    font_family: "Noto Sans",
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
    margin_v: 40,
    display_mode: "word",
    animation: "pop",
  });

  const [openColorPicker, setOpenColorPicker] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"trim" | "style" | "timeline">("trim");

  // Subtitle events for active clip (parsed from ASS — simplified representation)
  const [subEvents, setSubEvents] = useState<Array<{ index: number; text: string; start: number; end: number }>>([]);

  useEffect(() => {
    if (!sessionId) { router.push("/"); return; }
    loadClips();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  const loadClips = async () => {
    try {
      const result = await getClips(sessionId);
      if (result.status === "error") { setError(result.error ?? "เกิดข้อผิดพลาด"); return; }
      setClips(result.clips);
      const urls: Record<number, string> = {};
      result.clips.forEach((c) => { urls[c.index] = c.download_url; });
      setDownloadUrls(urls);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "โหลดคลิปไม่ได้");
    } finally {
      setLoading(false);
    }
  };

  const handleStyleChange = async (updates: Partial<StyleConfig>) => {
    const newStyle = { ...globalStyle, ...updates };
    setGlobalStyle(newStyle);
    const clip = clips[activeClip];
    if (clip?.ass_path) {
      await patchGlobalStyle(sessionId, clip.index, newStyle).catch(() => {});
    }
  };

  const handleRender = async (clipIndex: number) => {
    setRendering((r) => ({ ...r, [clipIndex]: true }));
    try {
      const url = await renderClip(sessionId, clipIndex);
      setDownloadUrls((d) => ({ ...d, [clipIndex]: url }));
    } catch (e) {
      console.error("Render failed", e);
    } finally {
      setRendering((r) => ({ ...r, [clipIndex]: false }));
    }
  };

  const handleSubEdit = async (clipIndex: number, eventIdx: number, text: string) => {
    setSubEvents((evts) => evts.map((e) => e.index === eventIdx ? { ...e, text } : e));
    await patchSubtitle(sessionId, clipIndex, eventIdx, { text }).catch(() => {});
  };

  const handleSubTiming = async (clipIndex: number, eventIdx: number, start: number, end: number) => {
    setSubEvents((evts) => evts.map((e) => e.index === eventIdx ? { ...e, start, end } : e));
    await patchSubtitle(sessionId, clipIndex, eventIdx, { start, end }).catch(() => {});
  };

  if (loading) return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-center space-y-3">
        <Loader2 size={32} className="animate-spin mx-auto text-violet-400" />
        <p className="text-white/50">โหลดคลิป...</p>
      </div>
    </div>
  );

  if (error) return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-center space-y-4">
        <p className="text-red-400">❌ {error}</p>
        <button onClick={() => router.push("/")} className="px-6 py-2 bg-violet-600 rounded-xl text-white">
          กลับหน้าหลัก
        </button>
      </div>
    </div>
  );

  const clip = clips[activeClip];

  return (
    <div className="min-h-screen flex flex-col">
      {/* Navbar */}
      <nav className="border-b border-white/10 px-6 py-3 flex items-center justify-between bg-black/30 backdrop-blur sticky top-0 z-40">
        <div className="flex items-center gap-3">
          <button onClick={() => router.push("/")} className="text-white/50 hover:text-white transition text-sm">← กลับ</button>
          <span className="text-white/20">|</span>
          <span className="font-semibold">แก้ไขคลิป</span>
        </div>
        <span className="text-xs text-white/30">{clips.length} คลิป · Session: {sessionId.slice(0, 8)}...</span>
      </nav>

      <div className="flex flex-1 overflow-hidden">
        {/* Clip list sidebar */}
        <div className="w-52 border-r border-white/10 flex flex-col bg-black/20 shrink-0 overflow-y-auto">
          <div className="p-3 text-xs text-white/40 font-medium uppercase tracking-wider">คลิปทั้งหมด</div>
          {clips.map((c, i) => (
            <button key={c.index}
              onClick={() => setActiveClip(i)}
              className={`p-3 text-left border-b border-white/5 transition ${activeClip === i ? "bg-violet-600/20 border-l-2 border-l-violet-500" : "hover:bg-white/5"}`}>
              <div className="font-medium text-sm text-white">คลิป {c.index}</div>
              <div className="text-xs text-white/40 mt-0.5">{c.start.toFixed(1)}s – {c.end.toFixed(1)}s</div>
              <div className="flex items-center gap-1 mt-1">
                <div className="h-1 flex-1 bg-white/10 rounded-full overflow-hidden">
                  <div className="h-full bg-violet-500 rounded-full" style={{ width: `${(c.score ?? 0) * 100}%` }} />
                </div>
                <span className="text-xs text-violet-300">{((c.score ?? 0) * 100).toFixed(0)}%</span>
              </div>
            </button>
          ))}
        </div>

        {/* Main editor area */}
        <div className="flex-1 flex overflow-hidden">
          {/* Video + controls */}
          <div className="flex-1 flex flex-col overflow-y-auto p-4 gap-4">
            {clip && (
              <>
                {/* Video player */}
                <div className="bg-black rounded-2xl overflow-hidden aspect-video">
                  <video
                    key={downloadUrls[clip.index] ?? clip.download_url}
                    src={`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}${clip.download_url}`}
                    controls
                    className="w-full h-full object-contain"
                  />
                </div>

                {/* Highlight reason */}
                {clip.highlight_reason && (
                  <div className="bg-violet-500/10 border border-violet-500/20 rounded-xl px-4 py-2 text-sm text-violet-200">
                    🤖 {clip.highlight_reason}
                  </div>
                )}

                {/* Tabs */}
                <div className="flex gap-1 bg-white/5 rounded-xl p-1">
                  {(["trim", "style", "timeline"] as const).map((t) => (
                    <button key={t} onClick={() => setActiveTab(t)}
                      className={`flex-1 py-2 rounded-lg text-sm font-medium transition ${activeTab === t ? "bg-violet-600 text-white" : "text-white/50 hover:text-white"}`}>
                      {t === "trim" ? "✂️ Trim" : t === "style" ? "🎨 สไตล์ซับ" : "📝 Timeline"}
                    </button>
                  ))}
                </div>

                {/* Trim panel */}
                {activeTab === "trim" && (
                  <div className="bg-white/5 border border-white/10 rounded-2xl p-5 space-y-4">
                    <h3 className="font-medium text-sm">ปรับขอบเขตคลิป (±10 วินาที)</h3>
                    <div className="space-y-3">
                      <div>
                        <label className="text-xs text-white/50">ขยายต้น ({trimStart[clip.index] ?? 0 > 0 ? "+" : ""}{trimStart[clip.index] ?? 0}s)</label>
                        <input type="range" min={-10} max={10} step={0.5}
                          value={trimStart[clip.index] ?? 0}
                          onChange={(e) => setTrimStart((t) => ({ ...t, [clip.index]: +e.target.value }))}
                          className="w-full mt-1" />
                        <div className="flex justify-between text-xs text-white/30 mt-0.5">
                          <span>-10s</span><span>0</span><span>+10s</span>
                        </div>
                      </div>
                      <div>
                        <label className="text-xs text-white/50">ขยายปลาย ({trimEnd[clip.index] ?? 0 > 0 ? "+" : ""}{trimEnd[clip.index] ?? 0}s)</label>
                        <input type="range" min={-10} max={10} step={0.5}
                          value={trimEnd[clip.index] ?? 0}
                          onChange={(e) => setTrimEnd((t) => ({ ...t, [clip.index]: +e.target.value }))}
                          className="w-full mt-1" />
                        <div className="flex justify-between text-xs text-white/30 mt-0.5">
                          <span>-10s</span><span>0</span><span>+10s</span>
                        </div>
                      </div>
                    </div>
                    <p className="text-xs text-white/30">
                      ความยาวใหม่: {(clip.duration + (trimEnd[clip.index] ?? 0) - (trimStart[clip.index] ?? 0)).toFixed(1)}s
                    </p>
                  </div>
                )}

                {/* Style panel */}
                {activeTab === "style" && clip.ass_path && (
                  <SubtitleStylePanel
                    style={globalStyle}
                    onChange={handleStyleChange}
                    openColorPicker={openColorPicker}
                    setOpenColorPicker={setOpenColorPicker}
                  />
                )}
                {activeTab === "style" && !clip.ass_path && (
                  <div className="bg-white/5 border border-white/10 rounded-2xl p-5 text-center text-white/40 text-sm">
                    ไม่มีซับไตเติ้ลในโหมด HRE (AI เลือกให้แล้ว)
                  </div>
                )}

                {/* Timeline panel */}
                {activeTab === "timeline" && clip.ass_path && (
                  <SubtitleTimeline
                    sessionId={sessionId}
                    clipIndex={clip.index}
                    events={subEvents}
                    onEdit={handleSubEdit}
                    onTiming={handleSubTiming}
                  />
                )}
                {activeTab === "timeline" && !clip.ass_path && (
                  <div className="bg-white/5 border border-white/10 rounded-2xl p-5 text-center text-white/40 text-sm">
                    ไม่มีซับไตเติ้ลในโหมด HRE
                  </div>
                )}
              </>
            )}
          </div>

          {/* Right panel: download */}
          <div className="w-52 border-l border-white/10 p-4 space-y-3 shrink-0">
            <h3 className="text-sm font-medium text-white/60">ดาวน์โหลด</h3>
            {clip && (
              <>
                <a
                  href={`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}${downloadUrls[clip.index] ?? clip.download_url}`}
                  download
                  className="flex items-center gap-2 w-full py-2.5 px-3 bg-white/10 hover:bg-white/20 rounded-xl text-sm transition text-white"
                >
                  <Download size={15} />
                  ดาวน์โหลดคลิป
                </a>

                {clip.ass_path && (
                  <button
                    onClick={() => handleRender(clip.index)}
                    disabled={rendering[clip.index]}
                    className="flex items-center gap-2 w-full py-2.5 px-3 bg-violet-600 hover:bg-violet-700 disabled:opacity-50 rounded-xl text-sm transition text-white"
                  >
                    {rendering[clip.index]
                      ? <Loader2 size={15} className="animate-spin" />
                      : <RotateCcw size={15} />}
                    {rendering[clip.index] ? "กำลัง Render..." : "Render & ดาวน์โหลด"}
                  </button>
                )}

                {/* Stats */}
                <div className="bg-white/5 rounded-xl p-3 space-y-1.5 text-xs">
                  <div className="flex justify-between"><span className="text-white/40">ช่วงเวลา</span><span>{clip.start.toFixed(1)}–{clip.end.toFixed(1)}s</span></div>
                  <div className="flex justify-between"><span className="text-white/40">ความยาว</span><span>{clip.duration.toFixed(1)}s</span></div>
                  <div className="flex justify-between"><span className="text-white/40">Score</span><span className="text-violet-300">{((clip.score ?? 0) * 100).toFixed(0)}%</span></div>
                </div>
              </>
            )}

            {/* Download all */}
            <div className="pt-3 border-t border-white/10">
              <p className="text-xs text-white/30 mb-2">ดาวน์โหลดทั้งหมด ({clips.length} คลิป)</p>
              {clips.map((c) => (
                <a key={c.index}
                  href={`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}${downloadUrls[c.index] ?? c.download_url}`}
                  download
                  className="flex items-center gap-1.5 py-1.5 text-xs text-white/50 hover:text-white transition">
                  <Download size={12} /> คลิป {c.index}
                </a>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ─── Subtitle Style Panel ─── */
function SubtitleStylePanel({
  style,
  onChange,
  openColorPicker,
  setOpenColorPicker,
}: {
  style: StyleConfig;
  onChange: (s: Partial<StyleConfig>) => void;
  openColorPicker: string | null;
  setOpenColorPicker: (k: string | null) => void;
}) {
  const colorFields = [
    { key: "primary_color", label: "สีตัวอักษรหลัก" },
    { key: "secondary_color", label: "สีก่อน Karaoke" },
    { key: "outline_color", label: "สีขอบ" },
    { key: "shadow_color", label: "สีเงา" },
  ];

  return (
    <div className="bg-white/5 border border-white/10 rounded-2xl p-5 space-y-5">
      <h3 className="font-medium text-sm">สไตล์ซับไตเติ้ล (Global)</h3>

      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1">
          <label className="text-xs text-white/50">ฟ้อนต์</label>
          <select value={style.font_family} onChange={(e) => onChange({ font_family: e.target.value })}
            className="w-full bg-white/5 border border-white/20 rounded-lg px-2 py-2 text-sm text-white focus:outline-none focus:border-violet-500">
            {FONTS.map((f) => <option key={f} value={f} className="bg-gray-900">{f}</option>)}
          </select>
        </div>
        <div className="space-y-1">
          <label className="text-xs text-white/50">ขนาด ({style.font_size}px)</label>
          <input type="range" min={20} max={96} step={2} value={style.font_size}
            onChange={(e) => onChange({ font_size: +e.target.value })} className="w-full mt-2" />
        </div>
        <div className="space-y-1">
          <label className="text-xs text-white/50">ขอบ ({style.outline_size}px)</label>
          <input type="range" min={0} max={10} step={0.5} value={style.outline_size}
            onChange={(e) => onChange({ outline_size: +e.target.value })} className="w-full mt-2" />
        </div>
        <div className="space-y-1">
          <label className="text-xs text-white/50">เงา ({style.shadow_size}px)</label>
          <input type="range" min={0} max={10} step={0.5} value={style.shadow_size}
            onChange={(e) => onChange({ shadow_size: +e.target.value })} className="w-full mt-2" />
        </div>
        <div className="space-y-1">
          <label className="text-xs text-white/50">Margin V ({style.margin_v}px)</label>
          <input type="range" min={0} max={200} step={5} value={style.margin_v}
            onChange={(e) => onChange({ margin_v: +e.target.value })} className="w-full mt-2" />
        </div>
        <div className="space-y-1">
          <label className="text-xs text-white/50">Spacing ({style.spacing ?? 0}px)</label>
          <input type="range" min={0} max={20} step={0.5} value={style.spacing ?? 0}
            onChange={(e) => onChange({ spacing: +e.target.value })} className="w-full mt-2" />
        </div>
        <div className="space-y-1">
          <label className="text-xs text-white/50">Scale X ({style.scale_x ?? 100}%)</label>
          <input type="range" min={50} max={200} step={5} value={style.scale_x ?? 100}
            onChange={(e) => onChange({ scale_x: +e.target.value })} className="w-full mt-2" />
        </div>
        <div className="space-y-1">
          <label className="text-xs text-white/50">Rotation ({style.angle ?? 0}°)</label>
          <input type="range" min={-45} max={45} step={1} value={style.angle ?? 0}
            onChange={(e) => onChange({ angle: +e.target.value })} className="w-full mt-2" />
        </div>
      </div>

      {/* Bold/Italic/Underline */}
      <div className="flex gap-2">
        {[{ k: "bold", l: "B", s: "font-bold" }, { k: "italic", l: "I", s: "italic" }, { k: "underline", l: "U", s: "underline" }].map(({ k, l }) => (
          <button key={k} onClick={() => onChange({ [k]: !(style as Record<string, unknown>)[k] })}
            className={`w-10 h-10 rounded-lg border text-sm transition ${(style as Record<string, unknown>)[k] ? "border-violet-500 bg-violet-600 text-white" : "border-white/20 bg-white/5 text-white/50 hover:text-white"}`}>
            {l}
          </button>
        ))}
      </div>

      {/* Colors */}
      <div className="grid grid-cols-2 gap-3">
        {colorFields.map(({ key, label }) => (
          <div key={key} className="space-y-1 relative">
            <label className="text-xs text-white/50">{label}</label>
            <button onClick={() => setOpenColorPicker(openColorPicker === key ? null : key)}
              className="w-full h-9 rounded-lg border border-white/20 flex items-center gap-2 px-2 hover:border-violet-400 transition">
              <span className="w-5 h-5 rounded border border-white/20" style={{ background: (style as Record<string, string>)[key] ?? "#fff" }} />
              <span className="text-xs text-white/60 font-mono">{(style as Record<string, string>)[key] ?? "#fff"}</span>
            </button>
            {openColorPicker === key && (
              <div className="absolute z-50 top-full mt-1 left-0">
                <div className="p-2 bg-gray-900 border border-white/20 rounded-xl shadow-2xl">
                  <HexColorPicker color={(style as Record<string, string>)[key] ?? "#fff"}
                    onChange={(c) => onChange({ [key]: c })} />
                  <button onClick={() => setOpenColorPicker(null)} className="mt-2 w-full text-xs text-white/40 hover:text-white">ปิด</button>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Opacity sliders */}
      <div className="grid grid-cols-2 gap-3 text-xs">
        <div className="space-y-1">
          <label className="text-white/50">ความโปร่งใสตัวอักษร</label>
          <input type="range" min={0} max={255} value={style.primary_alpha ?? 0}
            onChange={(e) => onChange({ primary_alpha: +e.target.value })} className="w-full" />
        </div>
        <div className="space-y-1">
          <label className="text-white/50">ความโปร่งใสขอบ</label>
          <input type="range" min={0} max={255} value={style.outline_alpha ?? 0}
            onChange={(e) => onChange({ outline_alpha: +e.target.value })} className="w-full" />
        </div>
        <div className="space-y-1">
          <label className="text-white/50">ความโปร่งใสเงา</label>
          <input type="range" min={0} max={255} value={style.shadow_alpha ?? 80}
            onChange={(e) => onChange({ shadow_alpha: +e.target.value })} className="w-full" />
        </div>
      </div>

      {/* Animation */}
      <div className="space-y-2">
        <label className="text-xs text-white/50">แอนิเมชัน</label>
        <div className="grid grid-cols-3 gap-1.5">
          {ANIMATIONS.map((a) => (
            <button key={a} onClick={() => onChange({ animation: a as StyleConfig["animation"] })}
              className={`py-2 rounded-lg text-xs transition ${style.animation === a ? "bg-violet-600 text-white" : "bg-white/5 text-white/50 border border-white/10 hover:text-white"}`}>
              {a}
            </button>
          ))}
        </div>
      </div>

      {/* Display mode */}
      <div className="space-y-2">
        <label className="text-xs text-white/50">รูปแบบการแสดงผล</label>
        <div className="flex gap-2">
          {[{ id: "word", label: "คำต่อคำ" }, { id: "sentence", label: "ประโยค" }].map(({ id, label }) => (
            <button key={id} onClick={() => onChange({ display_mode: id as "word" | "sentence" })}
              className={`flex-1 py-2 rounded-lg text-xs transition ${style.display_mode === id ? "bg-violet-600 text-white" : "bg-white/5 text-white/50 border border-white/10"}`}>
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Alignment */}
      <div className="space-y-2">
        <label className="text-xs text-white/50">ตำแหน่ง</label>
        <div className="grid grid-cols-3 gap-1 w-24">
          {ALIGNMENTS.map((a) => (
            <button key={a.val} onClick={() => onChange({ alignment: a.val })}
              className={`aspect-square rounded-lg text-xs font-bold transition ${style.alignment === a.val ? "bg-violet-600 text-white" : "bg-white/10 text-white/50 hover:bg-white/20"}`}>
              {a.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ─── Subtitle Timeline ─── */
function SubtitleTimeline({
  sessionId, clipIndex, events, onEdit, onTiming,
}: {
  sessionId: string;
  clipIndex: number;
  events: Array<{ index: number; text: string; start: number; end: number }>;
  onEdit: (ci: number, ei: number, text: string) => void;
  onTiming: (ci: number, ei: number, start: number, end: number) => void;
}) {
  if (!events.length) {
    return (
      <div className="bg-white/5 border border-white/10 rounded-2xl p-5 text-center text-white/40 text-sm">
        Timeline จะแสดงเมื่อ API ส่งข้อมูลซับไตเติ้ล
      </div>
    );
  }

  return (
    <div className="bg-white/5 border border-white/10 rounded-2xl p-4 space-y-2">
      <h3 className="font-medium text-sm mb-3">Timeline ซับไตเติ้ล</h3>
      <div className="space-y-2 max-h-80 overflow-y-auto">
        {events.map((evt) => (
          <div key={evt.index} className="flex gap-2 items-start bg-white/5 rounded-lg p-2">
            <div className="text-xs text-white/30 w-16 pt-1 shrink-0">
              {evt.start.toFixed(2)}s
            </div>
            <input
              value={evt.text}
              onChange={(e) => onEdit(clipIndex, evt.index, e.target.value)}
              className="flex-1 bg-transparent text-sm text-white focus:outline-none border-b border-white/20 focus:border-violet-500 pb-0.5 transition"
            />
            <div className="text-xs text-white/30 w-16 pt-1 shrink-0 text-right">
              {evt.end.toFixed(2)}s
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

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
