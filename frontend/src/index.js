import React from "react";
import ReactDOM from "react-dom/client";
import "@/index.css";
import App from "@/App";

// Suprime errores benignos que disparan el overlay de dev pero NO son accionables ni
// ocurren en produccion:
//  1) "ResizeObserver loop ..." (shadcn Select/Dialog).
//  2) "Script error." generico de scripts CROSS-ORIGIN (barra de preview de Emergent,
//     extensiones del navegador, widgets de terceros). Estos no traen archivo/linea ni
//     objeto Error, por eso no se pueden depurar. Los errores reales de nuestro bundle
//     SIEMPRE traen message/filename/lineno y objeto error, asi que no se suprimen.
const _isResizeObsErr = (msg) => typeof msg === "string" && msg.includes("ResizeObserver loop");
const _isMaskedScriptErr = (e) =>
  typeof e?.message === "string" && e.message.includes("Script error") &&
  !e?.error && (!e?.filename || e?.lineno === 0);
const _hideDevOverlay = () => {
  const o = document.getElementById("webpack-dev-server-client-overlay");
  if (o) o.style.display = "none";
};
window.addEventListener("error", (e) => {
  if (_isResizeObsErr(e.message) || _isMaskedScriptErr(e)) {
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
