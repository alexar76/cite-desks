import { useEffect, useState } from "react";
import { api } from "../lib/api";
import {
  currentPushSubscription,
  disableDeskPush,
  enableDeskPush,
  pwaSupported,
  registerDeskWorker,
} from "../lib/pwa";

type InstallEvent = Event & { prompt: () => Promise<void>; userChoice: Promise<{ outcome: string }> };

export function DeskPwa() {
  const [installEvent, setInstallEvent] = useState<InstallEvent | null>(null);
  const [standalone, setStandalone] = useState(false);
  const [pushOn, setPushOn] = useState(false);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const canPush = pwaSupported();

  useEffect(() => {
    void registerDeskWorker();
    const media = window.matchMedia("(display-mode: standalone)");
    const syncStandalone = () => setStandalone(media.matches || Boolean((navigator as Navigator & { standalone?: boolean }).standalone));
    syncStandalone();
    media.addEventListener("change", syncStandalone);
    const onPrompt = (event: Event) => {
      event.preventDefault();
      setInstallEvent(event as InstallEvent);
    };
    window.addEventListener("beforeinstallprompt", onPrompt);
    return () => {
      media.removeEventListener("change", syncStandalone);
      window.removeEventListener("beforeinstallprompt", onPrompt);
    };
  }, []);

  useEffect(() => {
    if (!canPush) return;
    api.pushStatus()
      .then(async (status) => {
        const sub = await currentPushSubscription();
        setPushOn(Boolean(status.subscribed && sub));
      })
      .catch(() => undefined);
  }, [canPush]);

  async function install() {
    if (!installEvent) return;
    setError("");
    await installEvent.prompt();
    const choice = await installEvent.userChoice;
    if (choice.outcome === "accepted") setInstallEvent(null);
  }

  async function togglePush() {
    setBusy("push");
    setError("");
    try {
      if (pushOn) {
        const sub = await currentPushSubscription();
        if (sub) await api.pushUnsubscribe(sub.toJSON() as { endpoint: string; keys: { p256dh: string; auth: string } });
        await disableDeskPush();
        setPushOn(false);
        return;
      }
      const status = await api.pushStatus();
      if (!status.enabled || !status.public_key) {
        throw new Error("Desk push is not configured on this host.");
      }
      const sub = await enableDeskPush(status.public_key);
      const json = sub.toJSON();
      if (!json.endpoint || !json.keys?.p256dh || !json.keys?.auth) {
        throw new Error("Browser did not return a complete push subscription.");
      }
      await api.pushSubscribe({
        endpoint: json.endpoint,
        keys: { p256dh: json.keys.p256dh, auth: json.keys.auth },
      });
      setPushOn(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Push failed.");
    } finally {
      setBusy("");
    }
  }

  return (
    <div className="pwa-box">
      <div className="kicker">This device</div>
      {installEvent && !standalone ? (
        <button className="btn btn-ember" type="button" onClick={() => void install()}>
          Install desk
        </button>
      ) : (
        <p className="muted">{standalone ? "Running as the installed desk." : "Install from the browser menu if the prompt does not appear."}</p>
      )}
      {canPush && (
        <button className="btn" type="button" disabled={busy === "push"} onClick={() => void togglePush()}>
          {pushOn ? "Disable push" : "Enable desk push"}
        </button>
      )}
      {error && <p className="err">{error}</p>}
    </div>
  );
}
