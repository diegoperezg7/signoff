import "./globals.css";
import "./signoff-skin.css";
import "./product-ui.css";
import "./chart-fixes.css";
import "./review-fixes.css";
import "./ui-refresh.css";
import "./reference-dashboard.css";
import "./design-system.css";
import type { ReactNode } from "react";
import { Inter } from "next/font/google";
import { AppProviders } from "../components/app-providers";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

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
      <body className={inter.variable}>
        <AppProviders>{children}</AppProviders>
      </body>
    </html>
  );
}
