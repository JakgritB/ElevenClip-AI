// Empty string = same-origin (works behind nginx on HF Spaces).
// Set NEXT_PUBLIC_API_URL for separate deployments (e.g. "http://server:8080").
const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

function demoHeaders(accessCode?: string): HeadersInit {
  return accessCode?.trim() ? { "X-Demo-Key": accessCode.trim() } : {};
}

export interface ProcessSettings {
  youtube_url?: string;
  use_demo_video?: boolean;
  channel_description: string;
  clip_style: string;
  target_duration: number;
  clip_count: number;
  clip_language: string;
  subtitle_language: string;
  mode: "normal" | "hre";
  style_config: StyleConfig;
}

export interface StyleConfig {
  font_family?: string;
  font_size?: number;
  primary_color?: string;
  secondary_color?: string;
  outline_color?: string;
  shadow_color?: string;
  primary_alpha?: number;
  outline_alpha?: number;
  shadow_alpha?: number;
  bold?: boolean;
  italic?: boolean;
  underline?: boolean;
  outline_size?: number;
  shadow_size?: number;
  alignment?: number;
  margin_l?: number;
  margin_r?: number;
  margin_v?: number;
  scale_x?: number;
  scale_y?: number;
  spacing?: number;
  angle?: number;
  display_mode?: "word" | "sentence";
  animation?: "none" | "fade" | "karaoke" | "pop" | "typewriter" | "bounce";
  fade_in_ms?: number;
  fade_out_ms?: number;
  subtitle_language?: string;
}

export interface SubtitleEvent {
  index: number;
  text: string;
  start: number;
  end: number;
}

export interface ClipResult {
  index: number;
  start: number;
  end: number;
  duration: number;
  score: number;
  download_url: string;
  raw_url: string;
  ass_path?: string;
  subtitle_events?: SubtitleEvent[];
  subtitle_event_count?: number;
  vision_analysis?: Record<string, unknown>;
  highlight_reason?: string;
}

export interface SessionResult {
  status: "starting" | "done" | "error";
  clips: ClipResult[];
  error?: string;
  last_progress?: { stage: string; pct: number; message: string };
}

export async function getVideoInfo(url: string, accessCode?: string) {
  const res = await fetch(`${API_BASE}/api/video-info`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...demoHeaders(accessCode) },
    body: JSON.stringify({ url }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function startProcessing(
  settings: ProcessSettings,
  file?: File,
  accessCode?: string
): Promise<string> {
  const formData = new FormData();
  formData.append("settings_json", JSON.stringify(settings));
  if (file) formData.append("file", file);

  const res = await fetch(`${API_BASE}/api/process`, {
    method: "POST",
    headers: demoHeaders(accessCode),
    body: formData,
  });
  if (!res.ok) throw new Error(await res.text());
  const { session_id } = await res.json();
  return session_id;
}

function _wsBase(): string {
  // If explicit API_BASE is set, derive ws:// from it.
  // Otherwise use the current page's host (works with nginx same-origin proxy).
  if (API_BASE) return API_BASE.replace(/^http/, "ws");
  if (typeof window === "undefined") return "ws://localhost:8080";
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}`;
}

export function connectProgressWS(
  sessionId: string,
  onMessage: (data: { stage: string; pct: number; message: string }) => void,
  onClose?: () => void
): WebSocket {
  const ws = new WebSocket(`${_wsBase()}/ws/progress/${sessionId}`);
  ws.onmessage = (e) => onMessage(JSON.parse(e.data));
  ws.onclose = () => onClose?.();
  return ws;
}

export async function getClips(sessionId: string): Promise<SessionResult> {
  const res = await fetch(`${API_BASE}/api/clips/${sessionId}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function patchSubtitle(
  sessionId: string,
  clipIndex: number,
  eventIndex: number,
  updates: Record<string, unknown>
) {
  await fetch(`${API_BASE}/api/clips/${sessionId}/${clipIndex}/subtitles`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ event_index: eventIndex, updates }),
  });
}

export async function patchGlobalStyle(
  sessionId: string,
  clipIndex: number,
  styleConfig: StyleConfig
) {
  await fetch(`${API_BASE}/api/clips/${sessionId}/${clipIndex}/style`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ style_config: styleConfig }),
  });
}

export async function renderClip(
  sessionId: string,
  clipIndex: number
): Promise<string> {
  const res = await fetch(`${API_BASE}/api/clips/${sessionId}/${clipIndex}/render`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(await res.text());
  const { download_url } = await res.json();
  return `${API_BASE}${download_url}`;
}
