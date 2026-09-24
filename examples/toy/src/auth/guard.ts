import { sessionFor } from "./session";
// Allows the request when the token belongs to the resource owner or an admin.
export function canRead(token: string, ownerId: string): boolean {
  const s = sessionFor(token);
  if (!s) return false;
  return s.admin || s.userId === ownerId;
}
