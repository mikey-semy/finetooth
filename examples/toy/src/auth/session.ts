// Session lookup for the toy app.
export function sessionFor(token: string): { userId: string; admin: boolean } | null {
  if (!token) return null;
  const [userId, role] = token.split(":");
  return { userId, admin: role === "admin" };
}
