# Backend (shared kernel)

This desk has **no private FastAPI tree**. Compose builds the API from the family kernel:

- Python package: [`../../kernel/desk_kernel/`](../../kernel/desk_kernel/)
- Entrypoint: `uvicorn desk_kernel.service.main:app` ([`../../kernel/Dockerfile`](../../kernel/Dockerfile))
- Desk identity: `DESK_ID=seamark` in [`../docker-compose.yml`](../docker-compose.yml)

Emberline alone keeps its own [`../../emberline/backend/`](../../emberline/backend/). Sibling desks (Tideline, Solrecord, Seamark, Plinth) share this rail.
