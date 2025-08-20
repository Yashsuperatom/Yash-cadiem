/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_BACKEND_URL: string
  // add more env vars here if needed
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
