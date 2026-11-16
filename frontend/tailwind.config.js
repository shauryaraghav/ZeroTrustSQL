export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: { extend: {
    colors: { ink: "#14202B", paper: "#F2F4F6", line: "#D5DBE1", accent: "#0E7C86", amber: "#B7791F", danger: "#9A3B3B" },
    fontFamily: { sans: ["Public Sans", "system-ui", "sans-serif"], mono: ["IBM Plex Mono", "ui-monospace", "monospace"] },
  } },
};
