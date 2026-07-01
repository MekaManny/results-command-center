import { type FormEvent, useEffect, useMemo, useState } from "react";
import { AlertTriangle, Clipboard, FilePlus2, MessageSquareText, Pencil, Plus, Search, Sparkles, X } from "lucide-react";
import { Layout } from "./components/Layout";
import { Badge, Button, Card, CardHeader, EmptyState, Field, TableWrap, inputClass } from "./components/UI";
import { contentJobs, leadSources, leadStatuses, leads, repPerformance, reps, stormCampaigns, type Lead, type LeadStatus } from "./data/mockData";
import { isOverdue, money, shortDate } from "./utils";

export type Page = "dashboard" | "leads" | "leadDetail" | "reps" | "storms" | "content" | "ai" | "admin";

const tableHead = "px-4 py-3 text-left text-xs font-black uppercase tracking-wide text-zinc-500";
const tableCell = "whitespace-nowrap px-4 py-3 text-sm text-zinc-700";
const TODAY = "2026-07-01";
const NEXT_FOLLOW_UP = "2026-07-08";
const LEADS_STORAGE_KEY = "results-command-center-leads";
const CONTENT_TASKS_STORAGE_KEY = "results-command-center-content-tasks";

type ContentTasksByLead = Record<string, string[]>;

const loadStoredLeads = () => {
  if (typeof window === "undefined") {
    return leads;
  }
  try {
    const stored = window.localStorage.getItem(LEADS_STORAGE_KEY);
    return stored ? (JSON.parse(stored) as Lead[]) : leads;
  } catch {
    return leads;
  }
};

const loadStoredContentTasks = () => {
  if (typeof window === "undefined") {
    return {};
  }
  try {
    const stored = window.localStorage.getItem(CONTENT_TASKS_STORAGE_KEY);
    return stored ? (JSON.parse(stored) as ContentTasksByLead) : {};
  } catch {
    return {};
  }
};

function Stat({ label, value, warn }: { label: string; value: string | number; warn?: boolean }) {
  return (
    <Card className="p-4">
      <p className="text-xs font-black uppercase tracking-wide text-zinc-500">{label}</p>
      <p className={`mt-2 text-2xl font-black ${warn ? "text-command-red" : "text-zinc-950"}`}>{value}</p>
    </Card>
  );
}

function Dashboard({ leadList, openLead }: { leadList: Lead[]; openLead: (lead: Lead) => void }) {
  const overdue = leadList.filter((lead) => isOverdue(lead.nextFollowUpDate));
  const totalPipeline = leadList.reduce((sum, lead) => sum + lead.estimatedValue, 0);
  return (
    <div className="grid gap-5 pb-16 lg:pb-0">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <Stat label="Open Leads" value={leadList.length} />
        <Stat label="New This Week" value={leadList.filter((lead) => lead.status === "New").length} />
        <Stat label="Follow-Ups Due" value={overdue.length} warn />
        <Stat label="Inspections This Week" value={4} />
        <Stat label="Estimates Sent" value={leadList.filter((lead) => lead.status === "Estimate Sent").length} />
        <Stat label="Sold Jobs" value={leadList.filter((lead) => lead.status === "Sold").length} />
        <Stat label="Storm Campaigns Live" value={stormCampaigns.filter((campaign) => campaign.status === "Active").length} />
        <Stat label="Content Opportunities" value={contentJobs.filter((job) => job.caption === "Ready").length} />
        <Stat label="Reviews To Request" value={contentJobs.filter((job) => job.review === "Needed").length} warn />
        <Stat label="Estimated Pipeline" value={money(totalPipeline)} />
      </div>

      <div className="grid gap-5 xl:grid-cols-[1.4fr_1fr]">
        <LeadTable title="Newest Lead Activity" rows={leadList.slice(0, 5)} openLead={openLead} />
        <LeadTable title="Follow-Ups Requiring Attention" rows={overdue} openLead={openLead} />
      </div>

      <div className="grid gap-5 xl:grid-cols-3">
        <Card>
          <CardHeader title="Rep Accountability Snapshot" />
          <div className="divide-y divide-zinc-100">
            {repPerformance.slice(0, 4).map((rep) => (
              <div key={rep.name} className="flex items-center justify-between px-5 py-3">
                <div>
                  <p className="font-bold">{rep.name}</p>
                  <p className="text-sm text-zinc-500">{rep.sold} sold • {rep.closeRate}% close</p>
                </div>
                {rep.overdue > 0 && <Badge tone="New">{rep.overdue} overdue</Badge>}
              </div>
            ))}
          </div>
        </Card>
        <Card>
          <CardHeader title="Storm Response Snapshot" />
          <div className="space-y-3 p-5">
            {stormCampaigns.slice(0, 3).map((campaign) => (
              <div key={`${campaign.city}-${campaign.neighborhood}`} className="rounded-md border border-zinc-200 p-3">
                <div className="flex items-center justify-between gap-3">
                  <p className="font-bold">{campaign.city} • {campaign.neighborhood}</p>
                  <Badge>{campaign.status}</Badge>
                </div>
                <p className="mt-1 text-sm text-zinc-500">{campaign.leadsGenerated} leads • {money(campaign.pipeline)}</p>
              </div>
            ))}
          </div>
        </Card>
        <Card>
          <CardHeader title="Jobs Ready For Content" />
          <div className="divide-y divide-zinc-100">
            {contentJobs.slice(0, 4).map((job) => (
              <div key={job.homeowner} className="px-5 py-3">
                <p className="font-bold">{job.homeowner}</p>
                <p className="text-sm text-zinc-500">{job.notes}</p>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}

function LeadTable({ title, rows, openLead }: { title: string; rows: Lead[]; openLead: (lead: Lead) => void }) {
  return (
    <Card>
      <CardHeader title={title} />
      <TableWrap>
        <table className="min-w-full">
          <thead className="bg-zinc-50">
            <tr>
              {["Name", "City", "Rep", "Status", "Follow-Up", "Value"].map((head) => <th key={head} className={tableHead}>{head}</th>)}
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-100">
            {rows.map((lead) => (
              <tr key={lead.id} onClick={() => openLead(lead)} className="cursor-pointer hover:bg-red-50/50">
                <td className={`${tableCell} font-bold text-zinc-950`}>{lead.name}</td>
                <td className={tableCell}>{lead.city}</td>
                <td className={tableCell}>{lead.assignedRep}</td>
                <td className={tableCell}><Badge>{lead.status}</Badge></td>
                <td className={tableCell}>{shortDate(lead.nextFollowUpDate)}</td>
                <td className={tableCell}>{money(lead.estimatedValue)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </TableWrap>
      {rows.length === 0 && <EmptyState text="No urgent follow-ups in this view." />}
    </Card>
  );
}

type SortKey = "none" | "createdDate" | "nextFollowUpDate" | "estimatedValue" | "status";
type SortDirection = "asc" | "desc";
type StormFilter = "All" | "Yes" | "No";
type LeadFormState = Omit<Lead, "id" | "timeline">;

const defaultLeadForm: LeadFormState = {
  name: "",
  phone: "",
  address: "",
  city: "",
  leadSource: leadSources[0],
  assignedRep: reps[0],
  status: "New",
  roofAge: 0,
  stormRelated: false,
  nextFollowUpDate: NEXT_FOLLOW_UP,
  lastContactedDate: TODAY,
  estimatedValue: 0,
  createdDate: TODAY,
  notes: "",
};

const statusRank = new Map<LeadStatus, number>(leadStatuses.map((item, index) => [item, index]));

function LeadModal({ mode, form, setForm, onClose, onSubmit }: { mode: "add" | "edit"; form: LeadFormState; setForm: (form: LeadFormState) => void; onClose: () => void; onSubmit: (event: FormEvent<HTMLFormElement>) => void }) {
  const update = <K extends keyof LeadFormState>(key: K, value: LeadFormState[K]) => setForm({ ...form, [key]: value });
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/45 p-4">
      <form onSubmit={onSubmit} className="max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-lg bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-zinc-200 px-5 py-4">
          <h2 className="text-lg font-black">{mode === "add" ? "Add Roofing Lead" : "Edit Lead Details"}</h2>
          <button type="button" onClick={onClose} className="grid h-9 w-9 place-items-center rounded-md text-zinc-500 hover:bg-zinc-100" aria-label="Close lead modal">
            <X size={19} />
          </button>
        </div>
        <div className="grid gap-4 p-5 md:grid-cols-2">
          <Field label="Name"><input required className={inputClass} value={form.name} onChange={(event) => update("name", event.target.value)} /></Field>
          <Field label="Phone"><input required className={inputClass} value={form.phone} onChange={(event) => update("phone", event.target.value)} /></Field>
          <Field label="Address"><input required className={inputClass} value={form.address} onChange={(event) => update("address", event.target.value)} /></Field>
          <Field label="City"><input required className={inputClass} value={form.city} onChange={(event) => update("city", event.target.value)} /></Field>
          <Field label="Lead Source">
            <select className={inputClass} value={form.leadSource} onChange={(event) => update("leadSource", event.target.value)}>
              {leadSources.map((item) => <option key={item}>{item}</option>)}
            </select>
          </Field>
          <Field label="Assigned Rep">
            <select className={inputClass} value={form.assignedRep} onChange={(event) => update("assignedRep", event.target.value)}>
              {reps.map((item) => <option key={item}>{item}</option>)}
            </select>
          </Field>
          <Field label="Status">
            <select className={inputClass} value={form.status} onChange={(event) => update("status", event.target.value as LeadStatus)}>
              {leadStatuses.map((item) => <option key={item}>{item}</option>)}
            </select>
          </Field>
          <Field label="Roof Age"><input min="0" className={inputClass} type="number" value={form.roofAge} onChange={(event) => update("roofAge", Number(event.target.value))} /></Field>
          <Field label="Next Follow-Up Date"><input required className={inputClass} type="date" value={form.nextFollowUpDate} onChange={(event) => update("nextFollowUpDate", event.target.value)} /></Field>
          <Field label="Last Contacted Date"><input required className={inputClass} type="date" value={form.lastContactedDate} onChange={(event) => update("lastContactedDate", event.target.value)} /></Field>
          <Field label="Estimated Value"><input min="0" className={inputClass} type="number" value={form.estimatedValue} onChange={(event) => update("estimatedValue", Number(event.target.value))} /></Field>
          <Field label="Created Date"><input required className={inputClass} type="date" value={form.createdDate} onChange={(event) => update("createdDate", event.target.value)} /></Field>
          <label className="flex h-10 items-center gap-2 self-end rounded-md border border-zinc-300 px-3 text-sm font-bold text-zinc-700">
            <input type="checkbox" checked={form.stormRelated} onChange={(event) => update("stormRelated", event.target.checked)} />
            Storm Related
          </label>
          <Field label="Notes"><textarea className={`${inputClass} min-h-24 py-2`} value={form.notes} onChange={(event) => update("notes", event.target.value)} /></Field>
        </div>
        <div className="flex justify-end gap-3 border-t border-zinc-200 px-5 py-4">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button type="submit">{mode === "add" ? "Create Lead" : "Save Lead"}</Button>
        </div>
      </form>
    </div>
  );
}

function LeadsPage({ leadList, setLeadList, openLead }: { leadList: Lead[]; setLeadList: React.Dispatch<React.SetStateAction<Lead[]>>; openLead: (lead: Lead) => void }) {
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("All");
  const [rep, setRep] = useState("All");
  const [source, setSource] = useState("All");
  const [storm, setStorm] = useState<StormFilter>("All");
  const [overdueOnly, setOverdueOnly] = useState(false);
  const [sortBy, setSortBy] = useState<SortKey>("none");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");
  const [modalMode, setModalMode] = useState<"add" | "edit" | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<LeadFormState>(defaultLeadForm);

  const filtered = useMemo(() => {
    const normalizedSearch = search.trim().toLowerCase();
    const visible = leadList.filter((lead) => {
      const text = `${lead.name} ${lead.phone} ${lead.address} ${lead.city} ${lead.leadSource} ${lead.assignedRep}`.toLowerCase();
      return text.includes(normalizedSearch)
      && (status === "All" || lead.status === status)
      && (rep === "All" || lead.assignedRep === rep)
      && (source === "All" || lead.leadSource === source)
      && (storm === "All" || (storm === "Yes" ? lead.stormRelated : !lead.stormRelated))
      && (!overdueOnly || isOverdue(lead.nextFollowUpDate));
    });

    if (sortBy === "none") {
      return visible;
    }

    return [...visible].sort((a, b) => {
      let result = 0;
      if (sortBy === "estimatedValue") {
        result = a.estimatedValue - b.estimatedValue;
      } else if (sortBy === "status") {
        result = (statusRank.get(a.status) ?? 0) - (statusRank.get(b.status) ?? 0);
      } else {
        result = new Date(`${a[sortBy]}T12:00:00`).getTime() - new Date(`${b[sortBy]}T12:00:00`).getTime();
      }
      return sortDirection === "asc" ? result : -result;
    });
  }, [leadList, search, status, rep, source, storm, overdueOnly, sortBy, sortDirection]);

  const clearFilters = () => {
    setSearch("");
    setStatus("All");
    setRep("All");
    setSource("All");
    setStorm("All");
    setOverdueOnly(false);
    setSortBy("none");
    setSortDirection("desc");
  };

  const openAddModal = () => {
    setEditingId(null);
    setForm(defaultLeadForm);
    setModalMode("add");
  };

  const openEditModal = (lead: Lead) => {
    setEditingId(lead.id);
    const { id: _id, timeline: _timeline, ...editableLead } = lead;
    setForm(editableLead);
    setModalMode("edit");
  };

  const closeModal = () => {
    setModalMode(null);
    setEditingId(null);
  };

  const handleSubmitLead = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (modalMode === "add") {
      const newLead: Lead = {
        ...form,
        id: `lead-${Date.now()}`,
        timeline: ["Lead created"],
      };
      setLeadList((current) => [newLead, ...current]);
    } else if (editingId) {
      setLeadList((current) => current.map((lead) => (lead.id === editingId ? { ...lead, ...form } : lead)));
    }
    closeModal();
  };

  const updateLeadStatus = (leadId: string, nextStatus: LeadStatus) => {
    setLeadList((current) => current.map((lead) => (lead.id === leadId ? { ...lead, status: nextStatus, timeline: [...lead.timeline, `Status updated to ${nextStatus}`] } : lead)));
  };

  return (
    <div className="grid gap-5 pb-16 lg:pb-0">
      <Card className="p-4">
        <div className="grid gap-3 lg:grid-cols-[1.4fr_1fr_1fr_1fr_1fr_auto]">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-3 text-zinc-400" size={16} />
            <input className={`${inputClass} w-full pl-9`} value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search homeowner, address, source, rep" />
          </div>
          <select aria-label="Status filter" className={inputClass} value={status} onChange={(event) => setStatus(event.target.value)}><option value="All">All Statuses</option>{leadStatuses.map((item) => <option key={item} value={item}>{item}</option>)}</select>
          <select aria-label="Assigned rep filter" className={inputClass} value={rep} onChange={(event) => setRep(event.target.value)}><option value="All">All Reps</option>{reps.map((item) => <option key={item} value={item}>{item}</option>)}</select>
          <select aria-label="Lead source filter" className={inputClass} value={source} onChange={(event) => setSource(event.target.value)}><option value="All">All Sources</option>{leadSources.map((item) => <option key={item} value={item}>{item}</option>)}</select>
          <select aria-label="Storm related filter" className={inputClass} value={storm} onChange={(event) => setStorm(event.target.value as StormFilter)}><option value="All">Storm + Retail</option><option value="Yes">Storm Related</option><option value="No">Retail / Repair</option></select>
          <Button onClick={openAddModal}><Plus size={17} />Add Roofing Lead</Button>
        </div>
        <div className="mt-3 grid gap-3 lg:grid-cols-[1fr_1fr_auto_auto]">
          <select aria-label="Sort leads" className={inputClass} value={sortBy} onChange={(event) => setSortBy(event.target.value as SortKey)}>
            <option value="none">Default Order</option>
            <option value="createdDate">Created Date</option>
            <option value="nextFollowUpDate">Next Follow-Up Date</option>
            <option value="estimatedValue">Estimated Value</option>
            <option value="status">Status</option>
          </select>
          <select aria-label="Sort direction" className={inputClass} value={sortDirection} onChange={(event) => setSortDirection(event.target.value as SortDirection)}>
            <option value="desc">Descending</option>
            <option value="asc">Ascending</option>
          </select>
          <label className="flex h-10 items-center gap-2 rounded-md border border-zinc-300 px-3 text-sm font-bold"><input type="checkbox" checked={overdueOnly} onChange={(event) => setOverdueOnly(event.target.checked)} /> Overdue Follow-Up</label>
          <Button variant="secondary" onClick={clearFilters}>Reset View</Button>
        </div>
      </Card>
      <Card>
        <CardHeader title="Lead Pipeline" eyebrow={`${filtered.length} visible`} />
        <TableWrap>
          <table className="min-w-full">
            <thead className="bg-zinc-50">
              <tr>{["Name", "Phone", "Address", "City", "Lead Source", "Assigned Rep", "Status", "Roof Age", "Storm", "Next Follow-Up", "Last Contacted", "Est. Value", "Created", "Actions"].map((head) => <th key={head} className={tableHead}>{head}</th>)}</tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {filtered.map((lead) => (
                <tr key={lead.id} onClick={() => openLead(lead)} className="cursor-pointer hover:bg-red-50/50">
                  <td className={`${tableCell} font-bold text-zinc-950`}>{lead.name}</td>
                  <td className={tableCell}>{lead.phone}</td>
                  <td className={tableCell}>{lead.address}</td>
                  <td className={tableCell}>{lead.city}</td>
                  <td className={tableCell}>{lead.leadSource}</td>
                  <td className={tableCell}>{lead.assignedRep}</td>
                  <td className={tableCell}><Badge>{lead.status}</Badge></td>
                  <td className={tableCell}>{lead.roofAge} yrs</td>
                  <td className={tableCell}>{lead.stormRelated ? "Yes" : "No"}</td>
                  <td className={tableCell}>{shortDate(lead.nextFollowUpDate)}</td>
                  <td className={tableCell}>{shortDate(lead.lastContactedDate)}</td>
                  <td className={tableCell}>{money(lead.estimatedValue)}</td>
                  <td className={tableCell}>{shortDate(lead.createdDate)}</td>
                  <td className={`${tableCell} min-w-72`} onClick={(event) => event.stopPropagation()}>
                    <div className="flex items-center gap-2">
                      <select aria-label={`Update ${lead.name} status`} className={`${inputClass} w-44`} value={lead.status} onChange={(event) => updateLeadStatus(lead.id, event.target.value as LeadStatus)}>
                        {leadStatuses.map((item) => <option key={item}>{item}</option>)}
                      </select>
                      <Button variant="secondary" onClick={() => openEditModal(lead)}><Pencil size={16} />Edit</Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableWrap>
        {filtered.length === 0 && <EmptyState text="No leads match the current view." />}
      </Card>
      {modalMode && <LeadModal mode={modalMode} form={form} setForm={setForm} onClose={closeModal} onSubmit={handleSubmitLead} />}
    </div>
  );
}

type DetailAction = "note" | "status" | "followup" | "content" | null;

function LeadDetail({ lead, setPage, updateLead, contentTasks, addContentTask }: { lead: Lead; setPage: (page: Page) => void; updateLead: (leadId: string, changes: Partial<Lead>) => void; contentTasks: string[]; addContentTask: (leadId: string, task: string) => void }) {
  const [activeAction, setActiveAction] = useState<DetailAction>(null);
  const [noteDraft, setNoteDraft] = useState("");
  const [statusDraft, setStatusDraft] = useState<LeadStatus>(lead.status);
  const [generatedText, setGeneratedText] = useState("");
  const [feedback, setFeedback] = useState("");

  useEffect(() => {
    setStatusDraft(lead.status);
    setFeedback("");
    setGeneratedText("");
    setActiveAction(null);
    setNoteDraft("");
  }, [lead.id, lead.status]);

  const appendTimeline = (event: string) => [...lead.timeline, event];

  const saveNote = () => {
    const trimmed = noteDraft.trim();
    if (!trimmed) {
      setFeedback("Enter a note before saving.");
      return;
    }
    updateLead(lead.id, {
      notes: `${lead.notes}\n\n${TODAY}: ${trimmed}`.trim(),
      timeline: appendTimeline("Note added"),
    });
    setNoteDraft("");
    setFeedback("Note saved.");
  };

  const saveStatus = () => {
    updateLead(lead.id, {
      status: statusDraft,
      timeline: appendTimeline(`Status updated to ${statusDraft}`),
    });
    setFeedback(`Status updated to ${statusDraft}.`);
  };

  const generateFollowUp = () => {
    const text = `Hi ${lead.name.split(" ")[0]}, this is ${lead.assignedRep} with Results Roofing. I wanted to follow up on your ${lead.city} roof project and make sure you have what you need for the next step.`;
    setGeneratedText(text);
    setActiveAction("followup");
    setFeedback("Follow-up text generated.");
  };

  const markFollowUpComplete = () => {
    updateLead(lead.id, {
      lastContactedDate: TODAY,
      nextFollowUpDate: NEXT_FOLLOW_UP,
      timeline: appendTimeline("Follow-up completed"),
    });
    setFeedback(`Follow-up marked complete. Next follow-up set for ${shortDate(NEXT_FOLLOW_UP)}.`);
  };

  const createContentTask = () => {
    const task = `${TODAY}: Capture content assets for ${lead.name} at ${lead.address}.`;
    addContentTask(lead.id, task);
    updateLead(lead.id, {
      timeline: appendTimeline("Content task created"),
    });
    setActiveAction("content");
    setFeedback("Content task created.");
  };

  return (
    <div className="grid gap-5 pb-16 lg:grid-cols-[1fr_360px] lg:pb-0">
      <div className="grid gap-5">
        <Card className="p-5">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <button className="mb-3 text-sm font-bold text-command-red" onClick={() => setPage("leads")}>Back to Lead Pipeline</button>
              <h2 className="text-2xl font-black">{lead.name}</h2>
              <p className="mt-1 text-zinc-500">{lead.address}, {lead.city}</p>
            </div>
            <Badge>{lead.status}</Badge>
          </div>
          <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {[
              ["Phone", lead.phone],
              ["Assigned Rep", lead.assignedRep],
              ["Lead Source", lead.leadSource],
              ["Estimated Value", money(lead.estimatedValue)],
              ["Roof Age", `${lead.roofAge} years`],
              ["Storm Related", lead.stormRelated ? "Yes" : "No"],
              ["Next Follow-Up", shortDate(lead.nextFollowUpDate)],
              ["Last Contacted", shortDate(lead.lastContactedDate)],
            ].map(([label, value]) => (
              <div key={label} className="rounded-md bg-zinc-50 p-3">
                <p className="text-xs font-black uppercase tracking-wide text-zinc-500">{label}</p>
                <p className="mt-1 font-bold">{value}</p>
              </div>
            ))}
          </div>
        </Card>
        <Card>
          <CardHeader title="Notes" />
          <p className="whitespace-pre-line p-5 text-sm leading-6 text-zinc-700">{lead.notes}</p>
        </Card>
        <Card>
          <CardHeader title="Activity Timeline" />
          <div className="space-y-4 p-5">
            {lead.timeline.map((event, index) => (
              <div key={`${event}-${index}`} className="flex gap-3">
                <div className="mt-1 h-3 w-3 rounded-full bg-command-red" />
                <div>
                  <p className="font-bold">{event}</p>
                  <p className="text-sm text-zinc-500">{shortDate(lead.createdDate)} + {index} days</p>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>
      <Card className="h-fit p-5">
        <h3 className="text-base font-black">Next Best Actions</h3>
        <div className="mt-4 grid gap-3">
          <Button variant="secondary" onClick={() => setActiveAction(activeAction === "note" ? null : "note")}><FilePlus2 size={17} />Log Note</Button>
          <Button variant="secondary" onClick={() => setActiveAction(activeAction === "status" ? null : "status")}><AlertTriangle size={17} />Change Pipeline Status</Button>
          <Button onClick={generateFollowUp}><Sparkles size={17} />Draft Follow-Up Text</Button>
          <Button variant="secondary" onClick={markFollowUpComplete}><Clipboard size={17} />Mark Follow-Up Complete</Button>
          <Button variant="secondary" onClick={createContentTask}><MessageSquareText size={17} />Create Content Task</Button>
        </div>
        {feedback && <div className="mt-4 rounded-md border border-green-200 bg-green-50 px-3 py-2 text-sm font-semibold text-green-800">{feedback}</div>}
        {activeAction === "note" && (
          <div className="mt-4 grid gap-3">
            <textarea className={`${inputClass} min-h-28 py-2`} value={noteDraft} onChange={(event) => setNoteDraft(event.target.value)} placeholder="Add a lead note" />
            <Button onClick={saveNote}>Save Note</Button>
          </div>
        )}
        {activeAction === "status" && (
          <div className="mt-4 grid gap-3">
            <select className={inputClass} value={statusDraft} onChange={(event) => setStatusDraft(event.target.value as LeadStatus)}>
              {leadStatuses.map((item) => <option key={item}>{item}</option>)}
            </select>
            <Button onClick={saveStatus}>Save Status</Button>
          </div>
        )}
        {generatedText && (
          <div className="mt-4 rounded-md border border-zinc-200 bg-zinc-50 p-3 text-sm leading-6 text-zinc-700">{generatedText}</div>
        )}
        {(activeAction === "content" || contentTasks.length > 0) && (
          <div className="mt-4 rounded-md border border-zinc-200 bg-zinc-50 p-3">
            <p className="text-sm font-black text-zinc-900">Content Tasks</p>
            {contentTasks.length === 0 ? (
              <p className="mt-2 text-sm text-zinc-500">No content tasks yet.</p>
            ) : (
              <ul className="mt-2 grid gap-2 text-sm text-zinc-700">
                {contentTasks.map((task, index) => <li key={`${task}-${index}`}>{task}</li>)}
              </ul>
            )}
          </div>
        )}
      </Card>
    </div>
  );
}

function RepPage() {
  return (
    <Card className="pb-2">
      <CardHeader title="Rep Accountability" />
      <TableWrap>
        <table className="min-w-full">
          <thead className="bg-zinc-50"><tr>{["Rep", "Leads", "Untouched", "Overdue", "Inspections", "Estimates", "Sold", "Lost", "Close Rate", "Pipeline"].map((head) => <th key={head} className={tableHead}>{head}</th>)}</tr></thead>
          <tbody className="divide-y divide-zinc-100">
            {repPerformance.map((rep) => (
              <tr key={rep.name}>
                <td className={`${tableCell} font-bold text-zinc-950`}>{rep.name}</td>
                <td className={tableCell}>{rep.leadsAssigned}</td>
                <td className={tableCell}>{rep.untouched}</td>
                <td className={tableCell}>{rep.overdue > 0 ? <Badge tone="New">{rep.overdue} overdue</Badge> : "0"}</td>
                <td className={tableCell}>{rep.inspections}</td>
                <td className={tableCell}>{rep.estimates}</td>
                <td className={tableCell}>{rep.sold}</td>
                <td className={tableCell}>{rep.lost}</td>
                <td className={tableCell}>{rep.closeRate}%</td>
                <td className={tableCell}>{money(rep.pipeline)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </TableWrap>
    </Card>
  );
}

function StormPage() {
  return (
    <div className="grid gap-5 pb-16 lg:pb-0">
      <div className="grid gap-4 md:grid-cols-4">
        <Stat label="Active Campaigns" value={stormCampaigns.filter((c) => c.status === "Active").length} />
        <Stat label="Target Homes" value={stormCampaigns.reduce((sum, c) => sum + c.targetHomes, 0)} />
        <Stat label="Leads Generated" value={stormCampaigns.reduce((sum, c) => sum + c.leadsGenerated, 0)} />
        <Stat label="Jobs Sold" value={stormCampaigns.reduce((sum, c) => sum + c.jobsSold, 0)} />
      </div>
      <Card>
        <CardHeader title="Storm Campaigns" />
        <TableWrap>
          <table className="min-w-full">
            <thead className="bg-zinc-50"><tr>{["Storm Date", "City", "Neighborhood", "Damage Type", "Target Homes", "Assigned Team", "Status", "Leads", "Sold", "Pipeline", "Notes"].map((head) => <th key={head} className={tableHead}>{head}</th>)}</tr></thead>
            <tbody className="divide-y divide-zinc-100">{stormCampaigns.map((campaign) => <tr key={`${campaign.city}-${campaign.neighborhood}`}><td className={tableCell}>{shortDate(campaign.stormDate)}</td><td className={`${tableCell} font-bold text-zinc-950`}>{campaign.city}</td><td className={tableCell}>{campaign.neighborhood}</td><td className={tableCell}>{campaign.damageType}</td><td className={tableCell}>{campaign.targetHomes}</td><td className={tableCell}>{campaign.assignedTeam}</td><td className={tableCell}><Badge>{campaign.status}</Badge></td><td className={tableCell}>{campaign.leadsGenerated}</td><td className={tableCell}>{campaign.jobsSold}</td><td className={tableCell}>{money(campaign.pipeline)}</td><td className="min-w-72 px-4 py-3 text-sm text-zinc-700">{campaign.notes}</td></tr>)}</tbody>
          </table>
        </TableWrap>
      </Card>
    </div>
  );
}

function ContentPage() {
  const cols = ["Job/Homeowner", "Address", "Rep", "Job Status", "Before", "Damage", "After", "Drone", "Testimonial", "Review", "Caption", "Posted", "Drive Folder", "Notes"];
  return (
    <Card>
      <CardHeader title="Content Bank" />
      <TableWrap>
        <table className="min-w-full">
          <thead className="bg-zinc-50"><tr>{cols.map((head) => <th key={head} className={tableHead}>{head}</th>)}</tr></thead>
          <tbody className="divide-y divide-zinc-100">
            {contentJobs.map((job) => (
              <tr key={job.homeowner}>
                <td className={`${tableCell} font-bold text-zinc-950`}>{job.homeowner}</td><td className={tableCell}>{job.address}</td><td className={tableCell}>{job.rep}</td><td className={tableCell}>{job.jobStatus}</td>
                {[job.beforePhotos, job.damagePhotos, job.afterPhotos, job.droneFootage, job.testimonial, job.review, job.caption, job.posted].map((status, idx) => <td key={`${job.homeowner}-${idx}`} className={tableCell}><Badge>{status}</Badge></td>)}
                <td className={tableCell}>{job.driveUrl}</td><td className="min-w-72 px-4 py-3 text-sm text-zinc-700">{job.notes}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </TableWrap>
    </Card>
  );
}

function AiPage() {
  const tools = ["Homeowner Follow-Up Text", "Stale Lead Reactivation Text", "Review Request Text", "Realtor Referral Message", "Storm Damage Outreach Text", "Before/After Social Caption", "Recruiting Post Caption"];
  const [tool, setTool] = useState(tools[0]);
  const [leadId, setLeadId] = useState(leads[0].id);
  const [notes, setNotes] = useState("");
  const lead = leads.find((item) => item.id === leadId)!;
  const [output, setOutput] = useState("");
  const [generatedType, setGeneratedType] = useState("");
  const firstName = lead.name.split(" ")[0];
  const contextLine = notes.trim() ? ` Also, please mention this context: ${notes.trim()}.` : "";
  const projectLine = `${lead.city} roof project at ${lead.address}`;
  const stormLine = lead.stormRelated ? "after the recent hail and wind activity" : "for your roof project";
  const contentJob = contentJobs.find((job) => job.homeowner === lead.name);
  const contentStatus = contentJob?.jobStatus || lead.status || "Not marked";

  const generateMessage = () => {
    const templates: Record<string, string> = {
      "Homeowner Follow-Up Text": `Hi ${firstName}, this is ${lead.assignedRep} with Results Roofing. I wanted to check in on your ${projectLine}. I see the current status is ${lead.status.toLowerCase()}, and I wanted to make sure you have what you need for the next step, whether that is inspection timing, estimate questions, or insurance guidance.${contextLine} Would today or tomorrow be better for a quick update?`,
      "Stale Lead Reactivation Text": `Hi ${firstName}, this is ${lead.assignedRep} with Results Roofing. We have not heard back about your ${lead.city} roof project, so I wanted to see if you still want help taking a look at the roof or moving the estimate forward.${contextLine} If now is not the right time, no problem at all. Should I keep this open for you or close it out?`,
      "Review Request Text": `Hi ${firstName}, this is ${lead.assignedRep} with Results Roofing. It was a pleasure helping with your completed ${lead.city} roof project. If you were happy with the experience, would you mind leaving us a quick review? It really helps other homeowners know who they can trust after a storm.${contextLine} Thank you again for choosing Results Roofing.`,
      "Realtor Referral Message": `Hi, this is ${lead.assignedRep} with Results Roofing. We help realtor partners protect their clients with roof inspections, storm damage documentation, and insurance guidance before or after a transaction. We recently worked around ${lead.city}, including projects like ${lead.address}.${contextLine} If you have a buyer, seller, or past client who needs a roof opinion, I would be happy to help.`,
      "Storm Damage Outreach Text": `Hi ${firstName}, this is ${lead.assignedRep} with Results Roofing. We are checking homes in ${lead.city} ${stormLine}. Hail and wind damage can be hard to spot from the ground, so we are offering a free roof inspection at ${lead.address}.${contextLine} Would you like us to take a quick look and let you know what we find?`,
      "Before/After Social Caption": `Another Results Roofing transformation in ${lead.city}. This ${lead.status.toLowerCase()} project at ${lead.address} is currently marked ${contentStatus.toLowerCase()} for content, and it shows what a clean inspection, clear communication, and quality install can do for a home.${contextLine} From roof concerns to finished result, our team is proud to help homeowners protect what matters most.`,
      "Recruiting Post Caption": `Results Roofing is looking for driven sales reps and roofing pros who want to win with a team that supports follow-up, storm response, and homeowner education. Our reps are helping homeowners across markets like ${lead.city} with inspections, estimates, and insurance guidance.${contextLine} If you are serious about growth and accountability, let us talk.`,
    };
    setGeneratedType(tool);
    setOutput(templates[tool]);
  };

  const handleToolChange = (nextTool: string) => {
    setTool(nextTool);
    setOutput("");
    setGeneratedType("");
  };

  const handleLeadChange = (nextLeadId: string) => {
    setLeadId(nextLeadId);
    setOutput("");
    setGeneratedType("");
  };

  const copyOutput = () => {
    if (output) {
      navigator.clipboard?.writeText(output);
    }
  };

  return (
    <div className="grid gap-5 pb-16 xl:grid-cols-[420px_1fr] lg:pb-0">
      <Card className="p-5">
        <div className="grid gap-4">
          <Field label="Message Type"><select className={inputClass} value={tool} onChange={(event) => handleToolChange(event.target.value)}>{tools.map((item) => <option key={item}>{item}</option>)}</select></Field>
          <Field label="Mock Lead / Job"><select className={inputClass} value={leadId} onChange={(event) => handleLeadChange(event.target.value)}>{leads.map((item) => <option key={item.id} value={item.id}>{item.name} • {item.city}</option>)}</select></Field>
          <Field label="Notes / Context"><textarea className={`${inputClass} min-h-32 py-2`} value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="Mention adjuster meeting, color choice, timing, or tone." /></Field>
          <Button onClick={generateMessage}><Sparkles size={17} />Generate Message</Button>
        </div>
      </Card>
      <Card>
        <CardHeader title={tool} action={<Button variant="secondary" onClick={copyOutput}><Clipboard size={17} />Copy Message</Button>} />
        <div className="border-b border-zinc-100 px-5 py-3">
          {generatedType ? (
            <p className="text-sm font-bold text-zinc-700">Generated: {generatedType}</p>
          ) : (
            <p className="text-sm font-bold text-zinc-500">Choose a message type, select a lead, add optional context, then generate a draft.</p>
          )}
        </div>
        {output ? (
          <textarea className="min-h-96 w-full resize-none border-0 bg-white p-5 text-sm leading-7 text-zinc-800 outline-none" value={output} readOnly />
        ) : (
          <div className="min-h-96 p-5">
            <EmptyState text="No AI draft generated yet." />
          </div>
        )}
      </Card>
    </div>
  );
}

function AdminPage() {
  const sections = [
    ["Sales Reps", reps],
    ["Lead Sources", leadSources],
    ["Pipeline Statuses", leadStatuses],
    ["Content Statuses", ["Missing", "Needed", "Uploaded", "Ready", "Posted", "Requested", "Received"]],
    ["Company Info", ["Results Roofing", "Dallas-Fort Worth", "(214) 555-0100", "ops@resultsroofing.example"]],
  ];
  return (
    <div className="grid gap-5 pb-16 md:grid-cols-2 xl:grid-cols-3 lg:pb-0">
      {sections.map(([title, values]) => (
        <Card key={title as string}>
          <CardHeader title={title as string} />
          <div className="grid gap-2 p-5">{(values as string[]).map((item) => <div key={item} className="rounded-md border border-zinc-200 px-3 py-2 text-sm font-semibold">{item}</div>)}</div>
        </Card>
      ))}
    </div>
  );
}

export default function App() {
  const [page, setPage] = useState<Page>("dashboard");
  const [leadList, setLeadList] = useState<Lead[]>(loadStoredLeads);
  const [selectedLeadId, setSelectedLeadId] = useState(leads[0].id);
  const [contentTasksByLead, setContentTasksByLead] = useState<ContentTasksByLead>(loadStoredContentTasks);
  const [sidebarOpen, setSidebarOpen] = useState(true);

  useEffect(() => {
    window.localStorage.setItem(LEADS_STORAGE_KEY, JSON.stringify(leadList));
  }, [leadList]);

  useEffect(() => {
    window.localStorage.setItem(CONTENT_TASKS_STORAGE_KEY, JSON.stringify(contentTasksByLead));
  }, [contentTasksByLead]);

  const selectedLead = leadList.find((lead) => lead.id === selectedLeadId) || leadList[0] || leads[0];

  const openLead = (lead: Lead) => {
    setSelectedLeadId(lead.id);
    setPage("leadDetail");
  };

  const updateLead = (leadId: string, changes: Partial<Lead>) => {
    setLeadList((current) => current.map((lead) => (lead.id === leadId ? { ...lead, ...changes } : lead)));
  };

  const addContentTask = (leadId: string, task: string) => {
    setContentTasksByLead((current) => ({
      ...current,
      [leadId]: [...(current[leadId] || []), task],
    }));
  };

  const content = {
    dashboard: <Dashboard leadList={leadList} openLead={openLead} />,
    leads: <LeadsPage leadList={leadList} setLeadList={setLeadList} openLead={openLead} />,
    leadDetail: <LeadDetail lead={selectedLead} setPage={setPage} updateLead={updateLead} contentTasks={contentTasksByLead[selectedLead.id] || []} addContentTask={addContentTask} />,
    reps: <RepPage />,
    storms: <StormPage />,
    content: <ContentPage />,
    ai: <AiPage />,
    admin: <AdminPage />,
  }[page];

  return <Layout page={page} setPage={setPage} sidebarOpen={sidebarOpen} setSidebarOpen={setSidebarOpen}>{content}</Layout>;
}
