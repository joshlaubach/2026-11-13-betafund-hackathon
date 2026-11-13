import type { Metadata } from "next";
import "@fontsource-variable/instrument-sans";
import "@fontsource-variable/literata";
import "katex/dist/katex.min.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "Echo",
  description: "Read a worksheet, mark it, see what to practice, and get new problems with honest labels.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
