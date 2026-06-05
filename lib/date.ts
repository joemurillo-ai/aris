export function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

export function daysBetween(fromIso: string, toIso = todayIso()): number {
  const from = new Date(`${fromIso}T00:00:00`);
  const to = new Date(`${toIso}T00:00:00`);
  return Math.floor((to.getTime() - from.getTime()) / 86400000);
}

export function isDueTodayOrEarlier(dateIso: string, today = todayIso()): boolean {
  return dateIso <= today;
}

export function formatShortDate(dateIso: string): string {
  return new Intl.DateTimeFormat("en", { month: "short", day: "numeric" }).format(new Date(`${dateIso}T00:00:00`));
}
