import "./globals.css";
import "./rentia-skin.css";
import "./product-ui.css";
import "./chart-fixes.css";
import "./review-fixes.css";
import "./ui-refresh.css";
import "./marketing.css";
import "./reference-dashboard.css";
import "./design-system.css";
import type { ReactNode } from "react";
import { Geist } from "next/font/google";
import { AppProviders } from "../components/app-providers";

const geist = Geist({ subsets: ["latin"], variable: "--font-geist" });

export const metadata = {
  title: "Signoff — Software delivery assurance",
  description: "From agreement to acceptance.",
  icons: {
    icon: "/icon.svg",
    apple: "/apple-icon.png",
  },
};
export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={geist.variable}>
        <AppProviders>{children}</AppProviders>
      </body>
    </html>
  );
}
