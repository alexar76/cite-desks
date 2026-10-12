export function money(value: number) {
  return `$${value.toFixed(2)}`;
}

export function when(value?: string | null) {
  if (!value) return "—";
  return new Date(value).toLocaleString("en-US", {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    timeZoneName: "short",
  });
}

export function shortDigest(value?: string | null) {
  if (!value) return "—";
  return `${value.slice(0, 10)}…${value.slice(-6)}`;
}
