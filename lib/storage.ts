"use client";

import { seedData } from "./seed";
import type { LedgerData } from "./types";

const STORAGE_KEY = "aris-relationship-ledger:v0.1";

export function loadLedgerData(): LedgerData {
  if (typeof window === "undefined") {
    return seedData;
  }

  const stored = window.localStorage.getItem(STORAGE_KEY);
  if (!stored) {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(seedData));
    return seedData;
  }

  try {
    return JSON.parse(stored) as LedgerData;
  } catch {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(seedData));
    return seedData;
  }
}

export function saveLedgerData(data: LedgerData): void {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
}

export function resetLedgerData(): LedgerData {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(seedData));
  return seedData;
}
