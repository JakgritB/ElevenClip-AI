import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ElevenClip AI — TikTok Highlight Clipper",
  description: "AI-powered livestream highlight extraction for TikTok. Powered by AMD ROCm + Qwen2.5-VL.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="th" className="h-full">
      <body className="min-h-full bg-[#0a0a1a] text-white antialiased">{children}</body>
    </html>
  );
}
