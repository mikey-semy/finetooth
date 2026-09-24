// Monthly quota: counts attempts, not successes — see finding H1-001.
export function quotaLeft(attempts: number, limit = 10): number {
  return Math.max(0, limit - attempts);
}
