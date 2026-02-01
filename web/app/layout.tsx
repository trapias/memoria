import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";
import { Navigation } from "@/components/navigation";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Memoria - Knowledge Graph Explorer",
  description: "Explore and manage memory relationships",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <Providers>
          <div className="min-h-screen flex flex-col">
            <Navigation />
            <main className="flex-1">{children}</main>
          </div>
        </Providers>
      </body>
    </html>
  );
}
