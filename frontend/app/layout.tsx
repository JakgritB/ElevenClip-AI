import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "ElevenClip AI — TikTok Highlight Clipper",
  description: "AI-powered livestream highlight extraction for TikTok. Powered by AMD ROCm + Qwen3-VL.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="th" className={`${inter.variable} h-full`}>
      <body className="min-h-full bg-[#0a0a1a] text-white antialiased">{children}</body>
    </html>
  );
}
