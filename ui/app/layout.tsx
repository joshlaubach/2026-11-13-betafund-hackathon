import type { Metadata } from "next";
import { GeistSans } from "geist/font/sans";
import "@fontsource/instrument-serif/400.css";
import "katex/dist/katex.min.css";
import "./globals.css";
import "./practice.css";
import { THEME_INIT_SCRIPT } from "@/lib/theme";

export const metadata: Metadata = {
  title: "Echo",
  description: "Read a worksheet, mark it, see what to practice, and get new problems with honest labels.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={GeistSans.variable} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      <body>
        {children}
      </body>
    </html>
  );
}
