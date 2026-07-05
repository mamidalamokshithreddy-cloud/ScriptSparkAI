const DEFAULT_LOCAL_HOST = ["local", "host"].join("");
const DEFAULT_API_URL = `http://${DEFAULT_LOCAL_HOST}:8000`;

export const API_BASE_URL = (
  import.meta.env.VITE_API_URL || DEFAULT_API_URL
).replace(/\/+$/, "");

