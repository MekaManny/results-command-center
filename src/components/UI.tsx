import type { ReactNode } from "react";

const statusStyles: Record<string, string> = {
  New: "bg-red-50 text-red-700 border-red-200",
  Contacted: "bg-zinc-100 text-zinc-700 border-zinc-200",
  "Inspection Scheduled": "bg-blue-50 text-blue-700 border-blue-200",
  "Inspection Completed": "bg-indigo-50 text-indigo-700 border-indigo-200",
  "Estimate Sent": "bg-amber-50 text-amber-700 border-amber-200",
  "Insurance Pending": "bg-orange-50 text-orange-700 border-orange-200",
  Sold: "bg-green-50 text-green-700 border-green-200",
  Lost: "bg-zinc-100 text-zinc-500 border-zinc-200",
  Completed: "bg-emerald-50 text-emerald-700 border-emerald-200",
  Paid: "bg-black text-white border-black",
  Active: "bg-red-50 text-red-700 border-red-200",
  Planning: "bg-zinc-100 text-zinc-700 border-zinc-200",
  "Follow-Up": "bg-amber-50 text-amber-700 border-amber-200",
  Missing: "bg-red-50 text-red-700 border-red-200",
  Needed: "bg-amber-50 text-amber-700 border-amber-200",
  Uploaded: "bg-blue-50 text-blue-700 border-blue-200",
  Ready: "bg-green-50 text-green-700 border-green-200",
  Posted: "bg-black text-white border-black",
  Requested: "bg-purple-50 text-purple-700 border-purple-200",
  Received: "bg-emerald-50 text-emerald-700 border-emerald-200",
};

export function Badge({ children, tone }: { children: ReactNode; tone?: string }) {
  const label = String(children);
  return (
    <span title={`Status: ${label}`} className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-semibold ${statusStyles[tone || label] || "bg-white text-zinc-700 border-zinc-200"}`}>
      {label}
    </span>
  );
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <section className={`min-w-0 rounded-lg border border-command-line bg-white shadow-panel ${className}`}>{children}</section>;
}

export function CardHeader({ title, action, eyebrow }: { title: string; action?: ReactNode; eyebrow?: string }) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-zinc-100 px-5 py-4">
      <div>
        {eyebrow && <p className="text-xs font-bold uppercase tracking-wide text-command-red">{eyebrow}</p>}
        <h2 className="text-base font-bold text-zinc-950">{title}</h2>
      </div>
      {action}
    </div>
  );
}

export function Button({ children, variant = "primary", onClick, type = "button" }: { children: ReactNode; variant?: "primary" | "secondary" | "ghost"; onClick?: () => void; type?: "button" | "submit" }) {
  const classes = {
    primary: "bg-command-red text-white hover:bg-red-800",
    secondary: "border border-zinc-300 bg-white text-zinc-900 hover:bg-zinc-50",
    ghost: "text-zinc-700 hover:bg-zinc-100",
  };
  return (
    <button type={type} onClick={onClick} className={`inline-flex h-10 items-center justify-center gap-2 rounded-md px-3 text-sm font-bold transition ${classes[variant]}`}>
      {children}
    </button>
  );
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="grid gap-1.5 text-sm font-semibold text-zinc-700">
      {label}
      {children}
    </label>
  );
}

export const inputClass = "h-10 rounded-md border border-zinc-300 bg-white px-3 text-sm text-zinc-950 outline-none focus:border-command-red focus:ring-2 focus:ring-red-100";

export function TableWrap({ children }: { children: ReactNode }) {
  return <div className="w-full overflow-x-auto">{children}</div>;
}

export function EmptyState({ text }: { text: string }) {
  return (
    <div className="px-5 py-10 text-center">
      <p className="text-sm font-bold text-zinc-800">{text}</p>
      <p className="mt-1 text-sm text-zinc-500">Adjust filters or add a new record to keep the workflow moving.</p>
    </div>
  );
}
