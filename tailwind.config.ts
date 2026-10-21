import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  darkMode: "class",
  theme: {
    // Owner constraint: border radius never exceeds 1px. Enforced at 0.
    borderRadius: {
      DEFAULT: "0px",
      sm: "0px",
      md: "0px",
      lg: "0px",
      xl: "0px",
      "2xl": "0px",
      "3xl": "0px",
      full: "0px",
    },
    borderWidth: {
      DEFAULT: "1px",
      "1.5": "1.5px",
      "2": "2px",
      "3": "3px",
    },
    extend: {
      colors: {
        primary: "#FF2D00",
        signal: "#00FF41",
        "background-dark": "#0D0E0D",
        "card-dark": "#141614",
        "card-hi": "#191C19",
        "border-dark": "#2A2D2B",
        "neutral-border": "#2A2D2B",
        "neutral-beige": "#F0EDE6",
        "dim-text": "#8C8C8C",
        "success-glow": "#00FF41",
        "selected-bg": "#1A0F0C",
      },
      fontFamily: {
        sans: ["var(--font-space-grotesk)"],
        mono: ["var(--font-plex-mono)"],
      },
    },
  },
  plugins: [],
};
export default config;
