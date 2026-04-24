module.exports = {
  content: [
    "./templates/**/*.html",
    "./static/js/**/*.js",
  ],
  theme: {
    extend: {
      colors: {
        primary: "#b89b86",
        secondary: "#5b8dcc",
        accent: "#34aa9a",
        emerald: {
          DEFAULT: "#10b981",
          500: "#10b981",
        },
        slate: {
          950: "#28292f",
        },
        surface: "rgba(255, 255, 255, 0.42)",
        "surface-light": "rgba(255, 255, 255, 0.66)",
      },
      fontFamily: {
        sans: ["Source Sans 3", "sans-serif"],
        heading: ["Lexend", "Source Sans 3", "sans-serif"],
      },
      boxShadow: {
        neon: "0 10px 28px rgba(48, 43, 38, 0.10)",
        "neon-pink": "0 10px 28px rgba(48, 43, 38, 0.10)",
      }
    },
  },
};
