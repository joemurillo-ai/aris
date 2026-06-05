"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { ArrowLeft, BriefcaseBusiness, CalendarClock, CheckCircle2, Clock3, RadioTower, ShieldAlert } from "lucide-react";
import { draftRelationshipBriefing } from "@/aris/briefing";
import { calculateRelationshipMomentum, getColdStatus } from "@/aris/scoring";
import { daysBetween, formatShortDate, todayIso } from "@/lib/date";
import { loadLedgerData, saveLedgerData } from "@/lib/storage";
import type { Commitment, FollowUpTask, Interaction, LedgerData, Opportunity } from "@/lib/types";
import { Card, Field, inputClass, Pill, ScoreBar } from "./ui";

function makeId(prefix: string) {
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export default function ContactProfile({ contactId }: { contactId: string }) {
  const [data, setData] = useState<LedgerData | null>(null);
  const [note, setNote] = useState("");
  const [taskTitle, setTaskTitle] = useState("");
  const [taskDate, setTaskDate] = useState(todayIso());
  const [opportunityTitle, setOpportunityTitle] = useState("");
  const [commitmentText, setCommitmentText] = useState("");
  const [commitmentDate, setCommitmentDate] = useState(todayIso());

  useEffect(() => {
    // localStorage is only available after the client mounts.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setData(loadLedgerData());
  }, []);

  useEffect(() => {
    if (data) saveLedgerData(data);
  }, [data]);

  const intelligence = useMemo(() => {
    if (!data) return null;
    const contact = data.contacts.find((item) => item.id === contactId);
    if (!contact) return null;
    const organization = data.organizations.find((item) => item.id === contact.organizationId);
    const interactions = data.interactions.filter((item) => item.contactId === contactId).sort((a, b) => b.date.localeCompare(a.date));
    const opportunities = data.opportunities.filter((item) => item.contactId === contactId).sort((a, b) => b.probability - a.probability);
    const commitments = data.commitments.filter((item) => item.contactId === contactId);
    const followUpTasks = data.followUpTasks.filter((item) => item.contactId === contactId);

    return {
      contact,
      organization,
      interactions,
      opportunities,
      commitments,
      followUpTasks,
      coldStatus: getColdStatus(contact),
      daysSinceInteraction: daysBetween(contact.lastInteractionDate)
    };
  }, [contactId, data]);

  if (!data) {
    return <main className="flex min-h-screen items-center justify-center text-slate-300">Loading profile...</main>;
  }

  if (!intelligence) {
    return (
      <main className="flex min-h-screen items-center justify-center p-6 text-center text-slate-300">
        <div>
          <p>Contact not found in the local ledger.</p>
          <Link href="/" className="mt-4 inline-flex rounded-md border border-white/10 px-3 py-2 text-sm font-semibold text-slate-200 hover:bg-white/10">
            Back to dashboard
          </Link>
        </div>
      </main>
    );
  }

  const briefing = draftRelationshipBriefing(intelligence);
  const momentum = calculateRelationshipMomentum(intelligence.contact, intelligence.interactions);

  function addInteraction() {
    if (!data || !note.trim()) return;
    const interaction: Interaction = { id: makeId("int"), contactId, date: todayIso(), channel: "Profile Note", summary: note, sentiment: "positive" };
    setData({
      ...data,
      interactions: [interaction, ...data.interactions],
      contacts: data.contacts.map((contact) => (contact.id === contactId ? { ...contact, lastInteractionDate: todayIso() } : contact))
    });
    setNote("");
  }

  function addTask() {
    if (!data || !taskTitle.trim()) return;
    const task: FollowUpTask = { id: makeId("task"), contactId, title: taskTitle, dueDate: taskDate, status: "open", priority: "Medium" };
    setData({
      ...data,
      followUpTasks: [task, ...data.followUpTasks],
      contacts: data.contacts.map((contact) => (contact.id === contactId ? { ...contact, nextFollowUpDate: taskDate } : contact))
    });
    setTaskTitle("");
  }

  function addOpportunity() {
    if (!data || !opportunityTitle.trim()) return;
    const opportunity: Opportunity = { id: makeId("opp"), contactId, title: opportunityTitle, value: "TBD", stage: "Signal", probability: 25, nextStep: "Define next move", targetDate: todayIso() };
    setData({ ...data, opportunities: [opportunity, ...data.opportunities] });
    setOpportunityTitle("");
  }

  function addCommitment() {
    if (!data || !commitmentText.trim()) return;
    const commitment: Commitment = { id: makeId("commit"), contactId, owner: "Joe", promise: commitmentText, dueDate: commitmentDate, status: "open" };
    setData({ ...data, commitments: [commitment, ...data.commitments] });
    setCommitmentText("");
  }

  return (
    <main className="min-h-screen px-4 py-5 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-6xl space-y-5">
        <Link href="/" className="inline-flex items-center gap-2 rounded-md border border-white/10 px-3 py-2 text-sm font-semibold text-slate-200 hover:bg-white/10">
          <ArrowLeft size={16} /> Dashboard
        </Link>

        <section className="grid gap-5 lg:grid-cols-[1.1fr_0.9fr]">
          <Card className="p-5">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.22em] text-signal-cyan">Relationship profile</p>
                <h1 className="mt-2 text-3xl font-semibold text-white">{intelligence.contact.name}</h1>
                <p className="mt-1 text-slate-400">{intelligence.contact.title} · {intelligence.organization?.name}</p>
              </div>
              <Pill tone={intelligence.coldStatus === "stable" ? "green" : intelligence.coldStatus === "watch" ? "gold" : "red"}>{intelligence.coldStatus}</Pill>
            </div>
            <p className="mt-5 text-sm leading-6 text-slate-300">{intelligence.contact.context}</p>
            <div className="mt-5 grid gap-4 sm:grid-cols-3">
              <Signal label="Trust" value={`${intelligence.contact.relationshipScore}/10`} />
              <Signal label="Strategic value" value={`${intelligence.contact.strategicValueScore}/10`} />
              <Signal label="Momentum" value={`${momentum}/10`} />
            </div>
            <div className="mt-5 grid gap-4 sm:grid-cols-2">
              <div>
                <p className="mb-2 text-xs text-slate-500">Relationship score</p>
                <ScoreBar value={intelligence.contact.relationshipScore} />
              </div>
              <div>
                <p className="mb-2 text-xs text-slate-500">Strategic value score</p>
                <ScoreBar value={intelligence.contact.strategicValueScore} />
              </div>
            </div>
          </Card>

          <Card className="p-5">
            <PanelTitle icon={<RadioTower size={18} />} title="ARIS briefing placeholder" />
            <h2 className="mt-4 text-xl font-semibold text-white">{briefing.headline}</h2>
            <p className="mt-3 text-sm text-slate-300">{briefing.risk}</p>
            <div className="mt-4 rounded-md border border-signal-cyan/20 bg-signal-cyan/10 p-3">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-signal-cyan">Next move</p>
              <p className="mt-2 text-sm text-slate-100">{briefing.nextMove}</p>
            </div>
            <ul className="mt-4 space-y-2 text-sm text-slate-400">
              {briefing.context.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </Card>
        </section>

        <section className="grid gap-5 lg:grid-cols-3">
          <Card>
            <PanelTitle icon={<ShieldAlert size={18} />} title="Risk and timing" />
            <div className="mt-4 space-y-3 text-sm text-slate-300">
              <p>{intelligence.daysSinceInteraction} days since the last captured interaction.</p>
              <p>Next follow-up: {formatShortDate(intelligence.contact.nextFollowUpDate)}</p>
              <p>{intelligence.contact.email}</p>
              <p>{intelligence.contact.phone}</p>
            </div>
          </Card>
          <Card>
            <PanelTitle icon={<BriefcaseBusiness size={18} />} title="Opportunities" />
            <div className="mt-4 space-y-3">
              {intelligence.opportunities.map((opportunity) => (
                <Intel key={opportunity.id} title={opportunity.title} meta={`${opportunity.stage} · ${opportunity.value} · ${opportunity.probability}%`} />
              ))}
              {!intelligence.opportunities.length && <Empty text="No opportunities attached." />}
            </div>
          </Card>
          <Card>
            <PanelTitle icon={<CalendarClock size={18} />} title="Follow-ups" />
            <div className="mt-4 space-y-3">
              {intelligence.followUpTasks.map((task) => (
                <Intel key={task.id} title={task.title} meta={`${formatShortDate(task.dueDate)} · ${task.priority}`} />
              ))}
              {!intelligence.followUpTasks.length && <Empty text="No follow-up tasks." />}
            </div>
          </Card>
        </section>

        <section className="grid gap-5 lg:grid-cols-[0.9fr_1.1fr]">
          <Card>
            <PanelTitle icon={<CheckCircle2 size={18} />} title="Add intelligence" />
            <div className="mt-4 space-y-4">
              <Field label="Interaction note">
                <textarea className={inputClass} rows={3} value={note} onChange={(event) => setNote(event.target.value)} />
              </Field>
              <button onClick={addInteraction} className="rounded-md border border-signal-cyan/30 px-3 py-2 text-sm font-semibold text-signal-cyan hover:bg-signal-cyan/10">
                Add note
              </button>
              <div className="grid gap-3 sm:grid-cols-[1fr_145px]">
                <Field label="Follow-up">
                  <input className={inputClass} value={taskTitle} onChange={(event) => setTaskTitle(event.target.value)} />
                </Field>
                <Field label="Date">
                  <input className={inputClass} type="date" value={taskDate} onChange={(event) => setTaskDate(event.target.value)} />
                </Field>
              </div>
              <button onClick={addTask} className="rounded-md border border-signal-gold/30 px-3 py-2 text-sm font-semibold text-signal-gold hover:bg-signal-gold/10">
                Add follow-up
              </button>
              <Field label="Opportunity">
                <input className={inputClass} value={opportunityTitle} onChange={(event) => setOpportunityTitle(event.target.value)} />
              </Field>
              <button onClick={addOpportunity} className="rounded-md border border-signal-green/30 px-3 py-2 text-sm font-semibold text-signal-green hover:bg-signal-green/10">
                Add opportunity
              </button>
              <div className="grid gap-3 sm:grid-cols-[1fr_145px]">
                <Field label="Commitment">
                  <input className={inputClass} value={commitmentText} onChange={(event) => setCommitmentText(event.target.value)} />
                </Field>
                <Field label="Due">
                  <input className={inputClass} type="date" value={commitmentDate} onChange={(event) => setCommitmentDate(event.target.value)} />
                </Field>
              </div>
              <button onClick={addCommitment} className="rounded-md border border-white/20 px-3 py-2 text-sm font-semibold text-slate-200 hover:bg-white/10">
                Add commitment
              </button>
            </div>
          </Card>

          <Card>
            <PanelTitle icon={<Clock3 size={18} />} title="Interaction timeline" />
            <div className="mt-4 space-y-3">
              {intelligence.interactions.map((interaction) => (
                <Intel key={interaction.id} title={`${formatShortDate(interaction.date)} · ${interaction.channel}`} meta={interaction.summary} />
              ))}
              {!intelligence.interactions.length && <Empty text="No interaction notes yet." />}
            </div>
            <div className="mt-5">
              <PanelTitle icon={<CheckCircle2 size={18} />} title="Commitments" />
              <div className="mt-4 space-y-3">
                {intelligence.commitments.map((commitment) => (
                  <Intel key={commitment.id} title={commitment.promise} meta={`${commitment.owner} · ${formatShortDate(commitment.dueDate)} · ${commitment.status}`} />
                ))}
                {!intelligence.commitments.length && <Empty text="No commitments captured." />}
              </div>
            </div>
          </Card>
        </section>
      </div>
    </main>
  );
}

function Signal({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-white/10 bg-command-950/50 p-3">
      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
    </div>
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

function Intel({ title, meta }: { title: string; meta: string }) {
  return (
    <div className="rounded-md border border-white/10 bg-command-950/50 p-3">
      <p className="font-medium text-white">{title}</p>
      <p className="mt-1 text-sm text-slate-400">{meta}</p>
    </div>
  );
}

function Empty({ text }: { text: string }) {
  return <p className="rounded-md border border-dashed border-white/10 p-4 text-sm text-slate-500">{text}</p>;
}
