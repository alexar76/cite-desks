import { useEffect } from "react";

export function PageMeta({ title, description }: { title: string; description?: string }) {
  useEffect(() => {
    const previous = document.title;
    document.title = title;
    const meta = document.querySelector('meta[name="description"]');
    const previousDescription = meta?.getAttribute("content") ?? "";
    if (meta && description) meta.setAttribute("content", description);
    return () => {
      document.title = previous;
      if (meta) meta.setAttribute("content", previousDescription);
    };
  }, [title, description]);
  return null;
}
