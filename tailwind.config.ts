import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  darkMode: "class",
  theme: {
    borderRadius: {
      DEFAULT: "0px",
      sm: "0px",
      md: "0px",
      lg: "0px",
      xl: "0px",
      "2xl": "0px",
      full: "0px",
    },
    borderWidth: {
      DEFAULT: "1px",
      "1.5": "1.5px",
    },
    extend: {
      colors: {
        primary: "#ff2f00",
        "background-dark": "#0E0E0E",
        "card-dark": "#1a1a1a",
        "border-dark": "#1e1e1e",
        "neutral-border": "#2a2a2a",
        "neutral-beige": "#F0EDE6",
        "dim-text": "#8c8c8c",
        "success-glow": "#00FF41",
        "selected-bg": "#140000",
      },
      fontFamily: {
        sans: ["var(--font-work-sans)"],
        serif: ["var(--font-playfair-display)"],
        mono: ["var(--font-ibm-plex-mono)"],
        "mono-jetbrains": ["var(--font-jetbrains-mono)"],
        "space-grotesk": ["var(--font-space-grotesk)"],
      },
      backgroundImage: {
        "gradient-radial": "radial-gradient(var(--tw-gradient-stops))",
        "gradient-conic":
          "conic-gradient(from 180deg at 50% 50%, var(--tw-gradient-stops))",
      },
    },
  },
  plugins: [],
};
export default config;
