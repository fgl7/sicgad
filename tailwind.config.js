/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./static/js/**/*.js",
  ],
  theme: {
    extend: {
      colors: {
        primary: "#2563eb",
        secondary: "#3b82f6",
        emerald: {
          DEFAULT: "#10b981",
          500: "#10b981",
        },
        slate: {
          950: "#020617",
        },
      },
      fontFamily: {
        sans: ["Source Sans 3", "Inter", "sans-serif"],
        heading: ["Lexend", "Source Sans 3", "sans-serif"],
      },
    },
  },
};
