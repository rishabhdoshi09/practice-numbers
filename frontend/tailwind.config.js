/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      colors: {
        buy:  { DEFAULT: "#22c55e", light: "#dcfce7", dark: "#15803d" },
        sell: { DEFAULT: "#ef4444", light: "#fee2e2", dark: "#b91c1c" },
        hold: { DEFAULT: "#f59e0b", light: "#fef3c7", dark: "#b45309" },
        surface: "#0f172a",
        panel:   "#1e293b",
        border:  "#334155",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "Fira Code", "monospace"],
      },
      animation: {
        "pulse-slow":    "pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "fade-in":       "fadeIn 0.4s ease-out",
        "slide-up":      "slideUp 0.35s ease-out",
        "glow-buy":      "glowBuy 2s ease-in-out infinite",
        "glow-sell":     "glowSell 2s ease-in-out infinite",
      },
      keyframes: {
        fadeIn:   { from: { opacity: 0 },              to: { opacity: 1 } },
        slideUp:  { from: { opacity: 0, transform: "translateY(20px)" }, to: { opacity: 1, transform: "translateY(0)" } },
        glowBuy:  { "0%,100%": { boxShadow: "0 0 20px rgba(34,197,94,0.3)" }, "50%": { boxShadow: "0 0 40px rgba(34,197,94,0.7)" } },
        glowSell: { "0%,100%": { boxShadow: "0 0 20px rgba(239,68,68,0.3)" }, "50%": { boxShadow: "0 0 40px rgba(239,68,68,0.7)" } },
      },
    },
  },
  plugins: [],
};
