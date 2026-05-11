import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CTI Agent — Multi-Agent Threat Intelligence",
  description:
    "LangGraph + MCP-powered agentic CTI platform with RAG, STIX KG, and IOC enrichment.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
