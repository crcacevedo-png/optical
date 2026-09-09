import React from "react";
import ReactDOM from "react-dom/client";
import "@/index.css";
import App from "@/App";

// Suprime el error benigno "ResizeObserver loop ..." (shadcn Select/Dialog) y oculta
// el overlay de dev que dispara (solo ante ESE error; no afecta otros errores ni producción).
const _isResizeObsErr = (msg) => typeof msg === "string" && msg.includes("ResizeObserver loop");
const _hideDevOverlay = () => {
  const o = document.getElementById("webpack-dev-server-client-overlay");
  if (o) o.style.display = "none";
};
window.addEventListener("error", (e) => {
  if (_isResizeObsErr(e.message)) {
    e.stopImmediatePropagation();
    e.preventDefault();
    _hideDevOverlay();
  }
}, true);
window.addEventListener("unhandledrejection", (e) => {
  if (_isResizeObsErr(e.reason?.message)) {
    e.preventDefault();
    _hideDevOverlay();
  }
});

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
