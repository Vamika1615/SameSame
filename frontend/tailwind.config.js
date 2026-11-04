/** @type {import('tailwindcss').Config} */
// Palette: coastal Sunseeker. Deep navy, dusty sky blue, warm cream and sand, one burnt-orange "sun" accent.
// Red stays reserved for "Looks the same, isn't".
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["'Inter Variable'", "system-ui", "sans-serif"],
        display: ["'Playfair Display Variable'", "Georgia", "serif"],
        mono: ["'JetBrains Mono Variable'", "ui-monospace", "monospace"],
      },
      colors: {
        accent: { 50: "#eef3f9", 100: "#d9e5f1", 200: "#b9cde3", 500: "#2a5590", 600: "#1f4677", 700: "#163a6b", 900: "#0d2445" },
        sun: { 50: "#fdf2e7", 100: "#f9ddc3", 500: "#e07b2e", 600: "#c9661f", 700: "#a35018" },
        sky: { 50: "#f2f6fa", 100: "#e3ecf4", 200: "#c9d9e9", 300: "#a7c0d8", 400: "#86a6c6", 500: "#6c8fb4" },
        ink: { DEFAULT: "#162a45", soft: "#3b4b63", mute: "#76829a" },
        paper: { DEFAULT: "#fffdf9", warm: "#f6efe3", line: "#e7dcc9" },
        sand: { 100: "#f3e8d6", 200: "#ead9bf", 300: "#dcc29d" },
        danger: { 50: "#fdf1ef", 500: "#d23c2f", 700: "#a8291f" },
        ok: { 50: "#eef8f2", 500: "#2f9461", 700: "#21714a" },
        warn: { 50: "#fdf4e3", 500: "#c47f17" },
      },
      fontSize: { base: ["17px", "1.55"] },  // projector-readable baseline
      boxShadow: {
        card: "0 1px 2px rgb(22 42 69 / .04), 0 8px 24px -12px rgb(22 42 69 / .18)",
        lift: "0 2px 4px rgb(22 42 69 / .06), 0 18px 40px -16px rgb(22 42 69 / .30)",
      },
      borderRadius: { "4xl": "2rem" },
    },
  },
  plugins: [],
};
