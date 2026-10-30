/** Per-process API token the server injects into index.html. Empty for the static site (it has no API). */
export function apiToken(): string {
  const meta = document.querySelector('meta[name="vb-token"]')?.getAttribute("content");
  return meta || (import.meta.env.VITE_VBISECT_TOKEN as string | undefined) || "";
}

export const withToken = (url: string, token = apiToken()) =>
  token ? `${url}${url.includes("?") ? "&" : "?"}token=${encodeURIComponent(token)}` : url;
