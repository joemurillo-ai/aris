import { daysBetween } from "@/lib/date";
import type { Contact, Interaction, Opportunity } from "@/lib/types";

export function getColdStatus(contact: Contact): "stable" | "watch" | "cold" {
  const days = daysBetween(contact.lastInteractionDate);
  if (contact.relationshipScore <= 4 || days >= 90) return "cold";
  if (contact.relationshipScore <= 6 || days >= 45) return "watch";
  return "stable";
}

export function calculateRelationshipMomentum(contact: Contact, interactions: Interaction[]): number {
  const recencyWeight = Math.max(0, 10 - Math.floor(daysBetween(contact.lastInteractionDate) / 10));
  const positiveSignals = interactions.filter((interaction) => interaction.sentiment === "positive").length;
  const watchSignals = interactions.filter((interaction) => interaction.sentiment === "watch").length;
  return Math.max(1, Math.min(10, Math.round((contact.relationshipScore + recencyWeight + positiveSignals - watchSignals) / 2)));
}

export function calculateOpportunityPriority(contact: Contact, opportunity: Opportunity): number {
  const stageBoost = opportunity.stage === "Active" ? 2 : opportunity.stage === "Committed" ? 3 : opportunity.stage === "Exploring" ? 1 : 0;
  return Math.max(1, Math.min(10, Math.round((contact.strategicValueScore + opportunity.probability / 10 + stageBoost) / 2)));
}
