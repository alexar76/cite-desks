import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { I18nProvider } from "./lib/I18nProvider";
import { registerDeskWorker } from "./lib/pwa";
import "./styles.css";

void registerDeskWorker();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ErrorBoundary
      fallback={
        <main className="main">
          Desk failed to render. <a href="/">Reload</a>
        </main>
      }
    >
      <I18nProvider>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </I18nProvider>
    </ErrorBoundary>
  </React.StrictMode>,
);
