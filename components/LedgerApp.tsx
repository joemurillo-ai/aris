"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, BriefcaseBusiness, CalendarClock, Check, Clock3, Plus, RotateCcw, Save, Trash2, UserRound, UsersRound } from "lucide-react";
import { getColdStatus } from "@/aris/scoring";
import { formatShortDate, isDueTodayOrEarlier, todayIso } from "@/lib/date";
import { loadLedgerData, resetLedgerData, saveLedgerData } from "@/lib/storage";
import type { Commitment, Contact, FollowUpTask, Interaction, LedgerData, Opportunity } from "@/lib/types";
import { Card, Field, inputClass, Pill, ScoreBar } from "./ui";

const emptyContact: Omit<Contact, "id"> = {
  name: "",
  title: "",
  organizationId: "org-northstar",
  domain: "insurance",
  email: "",
  phone: "",
  location: "",
  relationshipScore: 5,
  strategicValueScore: 5,
  lastInteractionDate: todayIso(),
  nextFollowUpDate: todayIso(),
  tags: [],
  context: ""
};

function makeId(prefix: string) {
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export default function LedgerApp() {
  const [data, setData] = useState<LedgerData | null>(null);
  const [selectedContactId, setSelectedContactId] = useState<string | null>(null);
  const [isAdding, setIsAdding] = useState(false);
  const [draft, setDraft] = useState<Omit<Contact, "id">>(emptyContact);

  useEffect(() => {
    // localStorage is only available after the client mounts.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setData(loadLedgerData());
  }, []);

  useEffect(() => {
    if (data) saveLedgerData(data);
  }, [data]);

  const dashboard = useMemo(() => {
    if (!data) return null;
    const contactsById = new Map(data.contacts.map((contact) => [contact.id, contact]));
    const dueTasks = data.followUpTasks.filter((task) => task.status === "open" && isDueTodayOrEarlier(task.dueDate));
    const coldContacts = data.contacts.filter((contact) => getColdStatus(contact) !== "stable");
    const topOpportunities = [...data.opportunities].sort((a, b) => b.probability - a.probability).slice(0, 4);
    const highValueContacts = [...data.contacts].sort((a, b) => b.strategicValueScore - a.strategicValueScore).slice(0, 5);
    const recentInteractions = [...data.interactions].sort((a, b) => b.date.localeCompare(a.date)).slice(0, 5);
    return { contactsById, dueTasks, coldContacts, topOpportunities, highValueContacts, recentInteractions };
  }, [data]);

  if (!data || !dashboard) {
    return <main className="flex min-h-screen items-center justify-center text-slate-300">Loading ARIS ledger...</main>;
  }

  const organizationsById = new Map(data.organizations.map((organization) => [organization.id, organization]));
  const selectedContact = data.contacts.find((contact) => contact.id === selectedContactId);

  function upsertContact() {
    if (!data || !draft.name.trim()) return;
    const contact: Contact = { ...draft, id: selectedContact?.id ?? makeId("contact"), tags: draft.tags.filter(Boolean) };
    const nextContacts = selectedContact ? data.contacts.map((item) => (item.id === selectedContact.id ? contact : item)) : [contact, ...data.contacts];
    setData({ ...data, contacts: nextContacts });
    setIsAdding(false);
    setSelectedContactId(contact.id);
  }

  function deleteContact(contactId: string) {
    if (!data) return;
    setData({
      ...data,
      contacts: data.contacts.filter((contact) => contact.id !== contactId),
      interactions: data.interactions.filter((interaction) => interaction.contactId !== contactId),
      opportunities: data.opportunities.filter((opportunity) => opportunity.contactId !== contactId),
      commitments: data.commitments.filter((commitment) => commitment.contactId !== contactId),
      followUpTasks: data.followUpTasks.filter((task) => task.contactId !== contactId)
    });
    setSelectedContactId(null);
  }

  function startEdit(contact: Contact) {
    setSelectedContactId(contact.id);
    setDraft({ ...contact });
    setIsAdding(true);
  }

  function addInteraction(contactId: string, summary: string) {
    if (!data || !summary.trim()) return;
    const interaction: Interaction = { id: makeId("int"), contactId, date: todayIso(), channel: "Note", summary, sentiment: "positive" };
    setData({
      ...data,
      interactions: [interaction, ...data.interactions],
      contacts: data.contacts.map((contact) => (contact.id === contactId ? { ...contact, lastInteractionDate: todayIso() } : contact))
    });
  }

  function addTask(contactId: string, title: string, dueDate: string) {
    if (!data || !title.trim()) return;
    const task: FollowUpTask = { id: makeId("task"), contactId, title, dueDate, status: "open", priority: "Medium" };
    setData({
      ...data,
      followUpTasks: [task, ...data.followUpTasks],
      contacts: data.contacts.map((contact) => (contact.id === contactId ? { ...contact, nextFollowUpDate: dueDate } : contact))
    });
  }

  function addOpportunity(contactId: string, title: string) {
    if (!data || !title.trim()) return;
    const opportunity: Opportunity = { id: makeId("opp"), contactId, title, value: "TBD", stage: "Signal", probability: 25, nextStep: "Define next move", targetDate: todayIso() };
    setData({ ...data, opportunities: [opportunity, ...data.opportunities] });
  }

  function addCommitment(contactId: string, promise: string, dueDate: string) {
    if (!data || !promise.trim()) return;
    const commitment: Commitment = { id: makeId("commit"), contactId, owner: "Joe", promise, dueDate, status: "open" };
    setData({ ...data, commitments: [commitment, ...data.commitments] });
  }

  return (
    <main className="min-h-screen px-4 py-5 sm:px-6 lg:px-8">
      <div className="mx-auto flex max-w-7xl flex-col gap-5">
        <header className="flex flex-col gap-4 border-b border-white/10 pb-5 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-signal-cyan">ARIS Relationship Ledger v0.1</p>
            <h1 className="mt-2 text-3xl font-semibold text-white sm:text-4xl">Executive relationship command center</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">
              Local-first relationship intelligence for trust, timing, commitments, opportunity, and strategic follow-through.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => {
                setDraft(emptyContact);
                setSelectedContactId(null);
                setIsAdding(true);
              }}
              className="inline-flex items-center gap-2 rounded-md bg-signal-cyan px-3 py-2 text-sm font-semibold text-command-950 transition hover:bg-cyan-200"
            >
              <Plus size={16} /> Contact
            </button>
            <button
              onClick={() => setData(resetLedgerData())}
              className="inline-flex items-center gap-2 rounded-md border border-white/10 px-3 py-2 text-sm font-semibold text-slate-200 transition hover:bg-white/10"
            >
              <RotateCcw size={16} /> Seed
            </button>
          </div>
        </header>

        <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Metric icon={<UsersRound size={18} />} label="Contacts" value={data.contacts.length.toString()} />
          <Metric icon={<CalendarClock size={18} />} label="Due Today" value={dashboard.dueTasks.length.toString()} tone="text-signal-gold" />
          <Metric icon={<AlertTriangle size={18} />} label="Cold Watch" value={dashboard.coldContacts.length.toString()} tone="text-signal-red" />
          <Metric icon={<BriefcaseBusiness size={18} />} label="Opportunities" value={data.opportunities.length.toString()} tone="text-signal-green" />
        </section>

        <section className="grid gap-5 xl:grid-cols-[1.1fr_0.9fr]">
          <Card>
            <PanelTitle icon={<CalendarClock size={18} />} title="Follow-ups due today" />
            <div className="mt-4 space-y-3">
              {dashboard.dueTasks.map((task) => {
                const contact = dashboard.contactsById.get(task.contactId);
                return (
                  <IntelRow key={task.id} title={task.title} meta={`${contact?.name ?? "Unknown"} · ${formatShortDate(task.dueDate)}`} tone={task.priority === "High" ? "red" : "gold"} />
                );
              })}
              {!dashboard.dueTasks.length && <EmptyLine text="No urgent follow-ups due." />}
            </div>
          </Card>

          <Card>
            <PanelTitle icon={<AlertTriangle size={18} />} title="Relationships going cold" />
            <div className="mt-4 space-y-3">
              {dashboard.coldContacts.slice(0, 5).map((contact) => (
                <button key={contact.id} onClick={() => setSelectedContactId(contact.id)} className="block w-full rounded-md border border-white/10 bg-command-950/50 p-3 text-left transition hover:border-signal-cyan/50">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="font-medium text-white">{contact.name}</p>
                      <p className="text-xs text-slate-400">{organizationsById.get(contact.organizationId)?.name}</p>
                    </div>
                    <Pill tone={getColdStatus(contact) === "cold" ? "red" : "gold"}>{getColdStatus(contact)}</Pill>
                  </div>
                </button>
              ))}
            </div>
          </Card>
        </section>

        <section className="grid gap-5 lg:grid-cols-3">
          <Card>
            <PanelTitle icon={<BriefcaseBusiness size={18} />} title="Top opportunities" />
            <div className="mt-4 space-y-3">
              {dashboard.topOpportunities.map((opportunity) => (
                <IntelRow
                  key={opportunity.id}
                  title={opportunity.title}
                  meta={`${dashboard.contactsById.get(opportunity.contactId)?.name ?? "Unknown"} · ${opportunity.value}`}
                  right={`${opportunity.probability}%`}
                  tone="green"
                />
              ))}
            </div>
          </Card>
          <Card>
            <PanelTitle icon={<UserRound size={18} />} title="High-value contacts" />
            <div className="mt-4 space-y-3">
              {dashboard.highValueContacts.map((contact) => (
                <button key={contact.id} onClick={() => setSelectedContactId(contact.id)} className="block w-full rounded-md border border-white/10 bg-command-950/50 p-3 text-left transition hover:border-signal-cyan/50">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="font-medium text-white">{contact.name}</p>
                      <p className="text-xs text-slate-400">{contact.title}</p>
                    </div>
                    <span className="text-lg font-semibold text-signal-cyan">{contact.strategicValueScore}</span>
                  </div>
                </button>
              ))}
            </div>
          </Card>
          <Card>
            <PanelTitle icon={<Clock3 size={18} />} title="Recent interactions" />
            <div className="mt-4 space-y-3">
              {dashboard.recentInteractions.map((interaction) => (
                <IntelRow key={interaction.id} title={dashboard.contactsById.get(interaction.contactId)?.name ?? "Unknown"} meta={interaction.summary} tone={interaction.sentiment === "watch" ? "gold" : "cyan"} />
              ))}
            </div>
          </Card>
        </section>

        <section className="grid gap-5 lg:grid-cols-[1fr_420px]">
          <Card>
            <div className="flex items-center justify-between gap-3">
              <PanelTitle icon={<UsersRound size={18} />} title="Relationship ledger" />
              <p className="text-xs text-slate-500">{data.contacts.length} local records</p>
            </div>
            <div className="mt-4 overflow-hidden rounded-lg border border-white/10">
              {data.contacts.map((contact) => (
                <div key={contact.id} className="grid gap-3 border-b border-white/10 bg-command-950/40 p-4 last:border-b-0 md:grid-cols-[1.2fr_1fr_0.8fr_0.8fr_auto] md:items-center">
                  <div>
                    <Link href={`/contacts/${contact.id}`} className="font-semibold text-white hover:text-signal-cyan">
                      {contact.name}
                    </Link>
                    <p className="text-sm text-slate-400">{contact.title}</p>
                  </div>
                  <div className="text-sm text-slate-300">{organizationsById.get(contact.organizationId)?.name}</div>
                  <div>
                    <p className="mb-1 text-xs text-slate-500">Trust {contact.relationshipScore}/10</p>
                    <ScoreBar value={contact.relationshipScore} />
                  </div>
                  <div>
                    <p className="mb-1 text-xs text-slate-500">Value {contact.strategicValueScore}/10</p>
                    <ScoreBar value={contact.strategicValueScore} />
                  </div>
                  <div className="flex gap-2 md:justify-end">
                    <button onClick={() => startEdit(contact)} className="rounded-md border border-white/10 px-3 py-2 text-xs font-semibold text-slate-200 hover:bg-white/10">
                      Edit
                    </button>
                    <button onClick={() => deleteContact(contact.id)} className="rounded-md border border-signal-red/20 px-3 py-2 text-xs font-semibold text-signal-red hover:bg-signal-red/10" aria-label={`Delete ${contact.name}`}>
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </Card>

          <ContactOps
            contact={selectedContact ?? data.contacts[0]}
            data={data}
            addInteraction={addInteraction}
            addTask={addTask}
            addOpportunity={addOpportunity}
            addCommitment={addCommitment}
          />
        </section>
      </div>

      {isAdding && (
        <div className="fixed inset-0 z-20 overflow-y-auto bg-command-950/80 p-4 backdrop-blur">
          <div className="mx-auto max-w-3xl rounded-lg border border-white/10 bg-command-900 p-5 shadow-glow">
            <div className="flex items-center justify-between gap-4">
              <h2 className="text-xl font-semibold text-white">{selectedContact ? "Edit contact" : "Add contact"}</h2>
              <button onClick={() => setIsAdding(false)} className="rounded-md border border-white/10 px-3 py-2 text-sm text-slate-300 hover:bg-white/10">
                Close
              </button>
            </div>
            <ContactForm draft={draft} setDraft={setDraft} organizations={data.organizations} onSave={upsertContact} />
          </div>
        </div>
      )}
    </main>
  );
}

function Metric({ icon, label, value, tone = "text-signal-cyan" }: { icon: React.ReactNode; label: string; value: string; tone?: string }) {
  return (
    <Card className="p-4">
      <div className="flex items-center justify-between gap-3">
        <span className={tone}>{icon}</span>
        <span className="text-2xl font-semibold text-white">{value}</span>
      </div>
      <p className="mt-3 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">{label}</p>
    </Card>
  );
}

function PanelTitle({ icon, title }: { icon: React.ReactNode; title: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-signal-cyan">{icon}</span>
      <h2 className="text-sm font-semibold uppercase tracking-[0.16em] text-slate-200">{title}</h2>
    </div>
  );
}

function IntelRow({ title, meta, right, tone = "neutral" }: { title: string; meta: string; right?: string; tone?: "neutral" | "green" | "gold" | "red" | "cyan" }) {
  return (
    <div className="rounded-md border border-white/10 bg-command-950/50 p-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-medium text-white">{title}</p>
          <p className="mt-1 line-clamp-2 text-sm text-slate-400">{meta}</p>
        </div>
        {right ? <Pill tone={tone}>{right}</Pill> : null}
      </div>
    </div>
  );
}

function EmptyLine({ text }: { text: string }) {
  return <p className="rounded-md border border-dashed border-white/10 p-4 text-sm text-slate-500">{text}</p>;
}

function ContactForm({
  draft,
  setDraft,
  organizations,
  onSave
}: {
  draft: Omit<Contact, "id">;
  setDraft: (draft: Omit<Contact, "id">) => void;
  organizations: LedgerData["organizations"];
  onSave: () => void;
}) {
  return (
    <div className="mt-5 grid gap-4 md:grid-cols-2">
      <Field label="Name">
        <input className={inputClass} value={draft.name} onChange={(event) => setDraft({ ...draft, name: event.target.value })} />
      </Field>
      <Field label="Title">
        <input className={inputClass} value={draft.title} onChange={(event) => setDraft({ ...draft, title: event.target.value })} />
      </Field>
      <Field label="Organization">
        <select className={inputClass} value={draft.organizationId} onChange={(event) => setDraft({ ...draft, organizationId: event.target.value })}>
          {organizations.map((organization) => (
            <option key={organization.id} value={organization.id}>
              {organization.name}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Domain">
        <select className={inputClass} value={draft.domain} onChange={(event) => setDraft({ ...draft, domain: event.target.value as Contact["domain"] })}>
          <option value="insurance">Insurance</option>
          <option value="ai">AI</option>
          <option value="mortgage">Mortgage</option>
          <option value="legal">Legal</option>
          <option value="personal-brand">Personal Brand</option>
        </select>
      </Field>
      <Field label="Email">
        <input className={inputClass} value={draft.email} onChange={(event) => setDraft({ ...draft, email: event.target.value })} />
      </Field>
      <Field label="Phone">
        <input className={inputClass} value={draft.phone} onChange={(event) => setDraft({ ...draft, phone: event.target.value })} />
      </Field>
      <Field label="Relationship score">
        <input className={inputClass} type="number" min={1} max={10} value={draft.relationshipScore} onChange={(event) => setDraft({ ...draft, relationshipScore: Number(event.target.value) })} />
      </Field>
      <Field label="Strategic value">
        <input className={inputClass} type="number" min={1} max={10} value={draft.strategicValueScore} onChange={(event) => setDraft({ ...draft, strategicValueScore: Number(event.target.value) })} />
      </Field>
      <Field label="Last interaction">
        <input className={inputClass} type="date" value={draft.lastInteractionDate} onChange={(event) => setDraft({ ...draft, lastInteractionDate: event.target.value })} />
      </Field>
      <Field label="Follow-up date">
        <input className={inputClass} type="date" value={draft.nextFollowUpDate} onChange={(event) => setDraft({ ...draft, nextFollowUpDate: event.target.value })} />
      </Field>
      <div className="md:col-span-2">
        <Field label="Relationship context">
          <textarea className={inputClass} rows={4} value={draft.context} onChange={(event) => setDraft({ ...draft, context: event.target.value })} />
        </Field>
      </div>
      <div className="md:col-span-2">
        <button onClick={onSave} className="inline-flex items-center gap-2 rounded-md bg-signal-cyan px-4 py-2 text-sm font-semibold text-command-950 transition hover:bg-cyan-200">
          <Save size={16} /> Save contact
        </button>
      </div>
    </div>
  );
}

function ContactOps({
  contact,
  data,
  addInteraction,
  addTask,
  addOpportunity,
  addCommitment
}: {
  contact: Contact;
  data: LedgerData;
  addInteraction: (contactId: string, summary: string) => void;
  addTask: (contactId: string, title: string, dueDate: string) => void;
  addOpportunity: (contactId: string, title: string) => void;
  addCommitment: (contactId: string, promise: string, dueDate: string) => void;
}) {
  const [note, setNote] = useState("");
  const [taskTitle, setTaskTitle] = useState("");
  const [taskDate, setTaskDate] = useState(todayIso());
  const [opportunityTitle, setOpportunityTitle] = useState("");
  const [commitmentText, setCommitmentText] = useState("");
  const [commitmentDate, setCommitmentDate] = useState(todayIso());
  const organization = data.organizations.find((item) => item.id === contact.organizationId);
  const commitments = data.commitments.filter((item) => item.contactId === contact.id);

  return (
    <Card>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Active profile</p>
          <h2 className="mt-2 text-2xl font-semibold text-white">{contact.name}</h2>
          <p className="text-sm text-slate-400">{contact.title} · {organization?.name}</p>
        </div>
        <Pill tone={getColdStatus(contact) === "stable" ? "green" : getColdStatus(contact) === "watch" ? "gold" : "red"}>{getColdStatus(contact)}</Pill>
      </div>

      <p className="mt-4 text-sm leading-6 text-slate-300">{contact.context}</p>
      <Link href={`/contacts/${contact.id}`} className="mt-4 inline-flex items-center gap-2 rounded-md border border-white/10 px-3 py-2 text-sm font-semibold text-slate-200 hover:bg-white/10">
        Open profile
      </Link>

      <div className="mt-5 space-y-4">
        <Field label="Add interaction note">
          <textarea className={inputClass} rows={3} value={note} onChange={(event) => setNote(event.target.value)} placeholder="Capture signal, trust movement, and context..." />
        </Field>
        <button
          onClick={() => {
            addInteraction(contact.id, note);
            setNote("");
          }}
          className="inline-flex items-center gap-2 rounded-md border border-signal-cyan/30 px-3 py-2 text-sm font-semibold text-signal-cyan hover:bg-signal-cyan/10"
        >
          <Plus size={16} /> Add note
        </button>

        <div className="grid gap-3 sm:grid-cols-[1fr_150px]">
          <Field label="Follow-up">
            <input className={inputClass} value={taskTitle} onChange={(event) => setTaskTitle(event.target.value)} placeholder="Next action" />
          </Field>
          <Field label="Date">
            <input className={inputClass} type="date" value={taskDate} onChange={(event) => setTaskDate(event.target.value)} />
          </Field>
        </div>
        <button
          onClick={() => {
            addTask(contact.id, taskTitle, taskDate);
            setTaskTitle("");
          }}
          className="inline-flex items-center gap-2 rounded-md border border-signal-gold/30 px-3 py-2 text-sm font-semibold text-signal-gold hover:bg-signal-gold/10"
        >
          <CalendarClock size={16} /> Add follow-up
        </button>

        <Field label="Opportunity">
          <input className={inputClass} value={opportunityTitle} onChange={(event) => setOpportunityTitle(event.target.value)} placeholder="Opportunity connected to this person" />
        </Field>
        <button
          onClick={() => {
            addOpportunity(contact.id, opportunityTitle);
            setOpportunityTitle("");
          }}
          className="inline-flex items-center gap-2 rounded-md border border-signal-green/30 px-3 py-2 text-sm font-semibold text-signal-green hover:bg-signal-green/10"
        >
          <BriefcaseBusiness size={16} /> Add opportunity
        </button>

        <div className="grid gap-3 sm:grid-cols-[1fr_150px]">
          <Field label="Commitment or promise">
            <input className={inputClass} value={commitmentText} onChange={(event) => setCommitmentText(event.target.value)} placeholder="Promise made by Joe or the contact" />
          </Field>
          <Field label="Due">
            <input className={inputClass} type="date" value={commitmentDate} onChange={(event) => setCommitmentDate(event.target.value)} />
          </Field>
        </div>
        <button
          onClick={() => {
            addCommitment(contact.id, commitmentText, commitmentDate);
            setCommitmentText("");
          }}
          className="inline-flex items-center gap-2 rounded-md border border-white/20 px-3 py-2 text-sm font-semibold text-slate-200 hover:bg-white/10"
        >
          <Check size={16} /> Add commitment
        </button>

        <div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Commitments</p>
          <div className="space-y-2">
            {commitments.map((commitment) => (
              <div key={commitment.id} className="rounded-md border border-white/10 bg-command-950/50 p-3">
                <div className="flex items-start gap-2">
                  <Check className="mt-0.5 text-signal-green" size={15} />
                  <p className="text-sm text-slate-300">{commitment.promise}</p>
                </div>
              </div>
            ))}
            {!commitments.length && <EmptyLine text="No commitments captured for this contact." />}
          </div>
        </div>
      </div>
    </Card>
  );
}
