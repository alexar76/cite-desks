import { useEffect } from "react";

export function PageMeta({ title, description, canonical }: { title: string; description?: string; canonical?: string }) {
  useEffect(() => {
    const previous = document.title;
    document.title = title;
    const meta = document.querySelector('meta[name="description"]');
    const previousDescription = meta?.getAttribute("content") ?? "";
    if (meta && description) meta.setAttribute("content", description);
    const link = document.querySelector('link[rel="canonical"]');
    const previousCanonical = link?.getAttribute("href") ?? "";
    if (link && canonical) link.setAttribute("href", canonical);
    return () => {
      if (link && canonical) link.setAttribute("href", previousCanonical);
      document.title = previous;
      if (meta) meta.setAttribute("content", previousDescription);
    };
  }, [title, description, canonical]);
  return null;
}
