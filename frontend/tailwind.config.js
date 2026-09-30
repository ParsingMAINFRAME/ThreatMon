/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: { extend: {
    colors: { ink: "#252a2b", panel: "#eeeae1", line: "#c8c8c0", signal: "#32596a", amber: "#896740", hazard: "#a14534", steel: "#697072", canvas: "#f5f2ea" },
    fontFamily: { sans: ["Arial", "Helvetica", "sans-serif"], mono: ["Consolas", "Courier New", "monospace"] },
  } },
  plugins: [],
};
