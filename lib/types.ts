export type RelationshipDomain = "insurance" | "ai" | "mortgage" | "legal" | "personal-brand";

export type OpportunityStage = "Signal" | "Exploring" | "Active" | "Committed" | "Dormant";

export type CommitmentStatus = "open" | "kept" | "at-risk" | "closed";

export type FollowUpStatus = "open" | "done";

export interface Organization {
  id: string;
  name: string;
  domain: RelationshipDomain;
  notes: string;
}

export interface Contact {
  id: string;
  name: string;
  title: string;
  organizationId: string;
  domain: RelationshipDomain;
  email: string;
  phone: string;
  location: string;
  relationshipScore: number;
  strategicValueScore: number;
  lastInteractionDate: string;
  nextFollowUpDate: string;
  tags: string[];
  context: string;
}

export interface Interaction {
  id: string;
  contactId: string;
  date: string;
  channel: string;
  summary: string;
  sentiment: "positive" | "neutral" | "watch";
}

export interface Opportunity {
  id: string;
  contactId: string;
  title: string;
  value: string;
  stage: OpportunityStage;
  probability: number;
  nextStep: string;
  targetDate: string;
}

export interface Commitment {
  id: string;
  contactId: string;
  owner: "Joe" | "Contact";
  promise: string;
  dueDate: string;
  status: CommitmentStatus;
}

export interface FollowUpTask {
  id: string;
  contactId: string;
  title: string;
  dueDate: string;
  status: FollowUpStatus;
  priority: "Low" | "Medium" | "High";
}

export interface LedgerData {
  organizations: Organization[];
  contacts: Contact[];
  interactions: Interaction[];
  opportunities: Opportunity[];
  commitments: Commitment[];
  followUpTasks: FollowUpTask[];
}

export interface ContactIntelligence {
  contact: Contact;
  organization?: Organization;
  interactions: Interaction[];
  opportunities: Opportunity[];
  commitments: Commitment[];
  followUpTasks: FollowUpTask[];
  coldStatus: "stable" | "watch" | "cold";
  daysSinceInteraction: number;
}
