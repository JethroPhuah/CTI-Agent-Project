import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: "#0b1020",
        panel: "#121a33",
        panel2: "#1a2547",
        border: "#243259",
        accent: "#5b9eff",
        accent2: "#8a6dff",
        good: "#4ade80",
        bad: "#f87171",
        warn: "#fbbf24",
        muted: "#7689b2",
      },
      fontFamily: {
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
    },
  },
  plugins: [],
};
export default config;
