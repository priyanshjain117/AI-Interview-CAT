import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        navy: {
          50: "#f5f7fb",
          100: "#e7ecf4",
          700: "#18345f",
          800: "#102849",
          900: "#0b1f3a"
        }
      },
      boxShadow: {
        panel: "0 10px 28px rgba(15, 23, 42, 0.08)"
      }
    }
  },
  plugins: []
};

export default config;
