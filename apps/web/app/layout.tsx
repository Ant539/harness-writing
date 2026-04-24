import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Paper Harness",
  description: "Skeleton UI for Paper Harness"
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
