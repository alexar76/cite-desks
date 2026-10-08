# Frontend (shared kernel web shell)

This desk has **no private React/Vite tree**. Compose serves the shared static shell:

- Markup / CSS / JS: [`../../kernel/web/`](../../kernel/web/)
  (`index.html`, `styles.css`, `app.js`, `scene.js`)
- Image: [`../../kernel/web/Dockerfile`](../../kernel/web/Dockerfile)

Emberline alone keeps its own React UI in [`../../emberline/frontend/`](../../emberline/frontend/).
