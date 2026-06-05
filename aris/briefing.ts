import { calculateRelationshipMomentum, getColdStatus } from "./scoring";
import type { ContactIntelligence } from "@/lib/types";

export interface RelationshipBriefing {
  headline: string;
  risk: string;
  nextMove: string;
  context: string[];
}

export function draftRelationshipBriefing(intelligence: ContactIntelligence): RelationshipBriefing {
  const momentum = calculateRelationshipMomentum(intelligence.contact, intelligence.interactions);
  const coldStatus = getColdStatus(intelligence.contact);
  const latestInteraction = intelligence.interactions[0];
  const openCommitment = intelligence.commitments.find((commitment) => commitment.status === "open" || commitment.status === "at-risk");
  const nextTask = intelligence.followUpTasks.find((task) => task.status === "open");

  return {
    headline: `${intelligence.contact.name} has momentum ${momentum}/10 with ${intelligence.contact.strategicValueScore}/10 strategic value.`,
    risk: coldStatus === "stable" ? "Relationship is active." : coldStatus === "watch" ? "Relationship needs attention before it cools." : "Relationship is cold or at risk.",
    nextMove: nextTask?.title ?? openCommitment?.promise ?? "Create a specific next step before the next conversation.",
    context: [
      latestInteraction ? `Last signal: ${latestInteraction.summary}` : "No interaction notes have been captured yet.",
      openCommitment ? `Open promise: ${openCommitment.promise}` : "No open commitments.",
      intelligence.opportunities[0] ? `Top opportunity: ${intelligence.opportunities[0].title}` : "No active opportunity attached."
    ]
  };
}

export async function generateAiBriefingPlaceholder(intelligence: ContactIntelligence): Promise<RelationshipBriefing> {
  // Future integration point: call OpenAI with prompts from aris/prompts.ts.
  return draftRelationshipBriefing(intelligence);
}
