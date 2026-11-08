import type { Metadata } from "next";
import "@fontsource-variable/public-sans"; // self-hosted: no build-time call to Google Fonts
import "./globals.css";

export const metadata: Metadata = {
  title: "Capital Insight",
  description: "All your money, one clear view.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en">
      <body className="min-h-screen font-sans antialiased">{children}</body>
    </html>
  );
}
