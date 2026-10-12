import { useEffect, useState, type ReactElement } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { api } from "./lib/api";
import { Archive } from "./pages/Archive";
import { Billing } from "./pages/Billing";
import { BriefPage } from "./pages/BriefPage";
import { BriefPublic } from "./pages/BriefPublic";
import { Desk } from "./pages/Desk";
import { Guide } from "./pages/Guide";
import { Landing } from "./pages/Landing";
import { Legal } from "./pages/Legal";
import { Login } from "./pages/Login";
import { InvoicePage } from "./pages/InvoicePage";
import { Ops } from "./pages/Ops";
import { Pay } from "./pages/Pay";
import { Press } from "./pages/Press";
import { RequestKey } from "./pages/RequestKey";
import { Sample } from "./pages/Sample";
import { Status } from "./pages/Status";
import { WatchDetail } from "./pages/WatchDetail";
import { WatchNew } from "./pages/WatchNew";

function Private({ children }: { children: ReactElement }) {
  const [ok, setOk] = useState<boolean | null>(null);
  useEffect(() => {
    api.me().then(() => setOk(true)).catch(() => setOk(false));
  }, []);
  if (ok === null) return <main className="main">Checking session…</main>;
  if (!ok) return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  return (
    <>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/sample" element={<Sample />} />
        <Route path="/guide" element={<Guide />} />
        <Route path="/press" element={<Press />} />
        <Route path="/request" element={<RequestKey />} />
        <Route path="/b/:token" element={<BriefPublic />} />
        <Route path="/login" element={<Login />} />
        <Route path="/pay" element={<Pay />} />
        <Route path="/pay/:invoiceId" element={<InvoicePage />} />
        <Route path="/status" element={<Status />} />
        <Route path="/ops" element={<Ops />} />
        <Route path="/legal" element={<Legal />} />
        <Route path="/desk" element={<Private><Desk /></Private>} />
        <Route path="/watches/new" element={<Private><WatchNew /></Private>} />
        <Route path="/watches/:id" element={<Private><WatchDetail /></Private>} />
        <Route path="/archive" element={<Private><Archive /></Private>} />
        <Route path="/billing" element={<Private><Billing /></Private>} />
        <Route path="/briefs/:id" element={<Private><BriefPage /></Private>} />
      </Routes>
    </>
  );
}
