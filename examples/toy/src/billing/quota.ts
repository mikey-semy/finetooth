// Monthly quota. Wrong on purpose: it counts attempts, and the user pays for our failures.
export function quotaLeft(attempts: number, limit = 10): number {
  return Math.max(0, limit - attempts);
}
