// Single source of truth for the backend origin.
// Set VITE_API_URL at build time (prod) or in the dev environment; falls back to
// the local-dev default so plain `npm run dev` still works out of the box.
export const API_BASE: string =
    (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '') ??
    'http://localhost:8000'
