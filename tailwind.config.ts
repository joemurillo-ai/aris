import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{js,ts,jsx,tsx,mdx}", "./components/**/*.{js,ts,jsx,tsx,mdx}", "./lib/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        command: {
          950: "#06080d",
          900: "#0b1018",
          800: "#111827",
          700: "#1f2937"
        },
        signal: {
          cyan: "#35d6d0",
          green: "#75e0a7",
          gold: "#f2c879",
          red: "#ff6b6b"
        }
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(53, 214, 208, 0.16), 0 20px 80px rgba(0, 0, 0, 0.35)"
      }
    }
  },
  plugins: []
};

export default config;
