import type { Metadata } from "next";
import "./styles.css";

export const metadata: Metadata = {
  title: "Express Intelligence OS",
  description: "Private, evidence-first log intelligence and team setup launcher for Express publications",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
