/** Where to go after logging in, from a `?next=` value: its path, query and hash if it points
 * at this site, else null. A link like `/login?next=//evil.example` must not send someone to
 * another site once they've logged in */
export function safeNext(next: string | null, origin = window.location.origin): string | null {
  if (!next?.startsWith('/')) return null
  let url: URL
  try {
    url = new URL(next, origin)
  } catch {
    return null
  }
  // Also catches `//host` and `/\host`, which browsers read as another site
  if (url.origin !== origin) return null
  return `${url.pathname}${url.search}${url.hash}`
}
