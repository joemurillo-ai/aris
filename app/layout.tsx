import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ARIS Relationship Ledger",
  description: "Local-first relationship intelligence system for Joe Murillo"
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
