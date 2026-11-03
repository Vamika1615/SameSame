/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["'Inter Variable'", "system-ui", "sans-serif"],
        mono: ["'JetBrains Mono Variable'", "ui-monospace", "monospace"],
      },
      colors: {
        // One confident accent (deep teal) on calm neutrals. Red is reserved for "Looks the same, isn't".
        accent: { 50: "#ecfbf9", 100: "#cff5f0", 500: "#0f9488", 600: "#0b7a70", 700: "#0a5f58", 900: "#073c38" },
        ink: { DEFAULT: "#0f172a", soft: "#334155", mute: "#64748b" },
        paper: { DEFAULT: "#ffffff", warm: "#f7f7f4", line: "#e5e5e0" },
        danger: { 50: "#fef2f2", 500: "#dc2626", 700: "#b91c1c" },
        ok: { 50: "#f0fdf4", 500: "#16a34a", 700: "#15803d" },
        warn: { 50: "#fffbeb", 500: "#d97706" },
      },
      fontSize: { base: ["17px", "1.55"] },  // projector-readable baseline
    },
  },
  plugins: [],
};
