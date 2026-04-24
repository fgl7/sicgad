module.exports = {
  content: [
    "./templates/**/*.html",
    "./static/js/**/*.js",
  ],
  theme: {
    extend: {
      colors: {
        primary: "#b052ff",
        secondary: "#ff2a85",
        accent: "#00d4ff",
        emerald: {
          DEFAULT: "#10b981",
          500: "#10b981",
        },
        slate: {
          950: "#140a28",
        },
        surface: "rgba(255, 255, 255, 0.03)",
        "surface-light": "rgba(255, 255, 255, 0.08)",
      },
      fontFamily: {
        sans: ["Inter", "sans-serif"],
        heading: ["Inter", "sans-serif"],
      },
      boxShadow: {
        neon: "0 0 15px rgba(176, 82, 255, 0.5)",
        "neon-pink": "0 0 15px rgba(255, 42, 133, 0.5)",
      }
    },
  },
};
