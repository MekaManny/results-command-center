import { BarChart3, Bot, BriefcaseBusiness, CloudLightning, FileImage, Home, Menu, Settings, UsersRound } from "lucide-react";
import type { Page } from "../App";

const nav = [
  { id: "dashboard", label: "Dashboard", icon: Home },
  { id: "leads", label: "Leads", icon: BriefcaseBusiness },
  { id: "reps", label: "Rep Accountability", icon: UsersRound },
  { id: "storms", label: "Storm Campaigns", icon: CloudLightning },
  { id: "content", label: "Content Bank", icon: FileImage },
  { id: "ai", label: "AI Assistant", icon: Bot },
  { id: "admin", label: "Admin Settings", icon: Settings },
] as const;

const descriptions: Record<Page, string> = {
  dashboard: "Leadership snapshot of pipeline, follow-ups, storms, and content readiness",
  leads: "Track homeowners from first touch through sold job",
  leadDetail: "Review homeowner details, activity, and next actions",
  reps: "Spot rep follow-up gaps and pipeline accountability",
  storms: "Monitor storm response campaigns and neighborhood production",
  content: "Track job assets needed for reviews, social proof, and recruiting",
  ai: "Draft homeowner, referral, review, and recruiting messages",
  admin: "Manage the mock setup values used in this prototype",
};

export function Layout({ page, setPage, children, sidebarOpen, setSidebarOpen }: { page: Page; setPage: (page: Page) => void; children: React.ReactNode; sidebarOpen: boolean; setSidebarOpen: (open: boolean) => void }) {
  const current = nav.find((item) => item.id === page)?.label || "Lead Detail";
  const navigate = (nextPage: Page) => {
    setPage(nextPage);
    if (window.innerWidth < 1024) {
      setSidebarOpen(false);
    }
  };
  return (
    <div className="min-h-screen bg-zinc-100 text-zinc-950">
      {sidebarOpen && <button type="button" aria-label="Close sidebar backdrop" className="fixed inset-0 z-10 bg-black/30 lg:hidden" onClick={() => setSidebarOpen(false)} />}
      <aside className={`fixed inset-y-0 left-0 z-20 w-72 border-r border-zinc-200 bg-command-black text-white shadow-xl transition-transform ${sidebarOpen ? "translate-x-0" : "-translate-x-full"}`}>
        <div className="flex h-20 items-center gap-3 border-b border-white/10 px-5">
          <div className="grid h-11 w-11 place-items-center rounded-md bg-command-red font-black">RC</div>
          <div>
            <p className="text-base font-black">Results</p>
            <p className="text-xs font-semibold text-zinc-400">Roofing Ops Prototype</p>
          </div>
        </div>
        <nav className="grid gap-1 px-3 py-5">
          {nav.map((item) => {
            const Icon = item.icon;
            const active = item.id === page;
            return (
              <button key={item.id} onClick={() => navigate(item.id)} className={`flex h-11 items-center gap-3 rounded-md px-3 text-left text-sm font-bold transition ${active ? "bg-command-red text-white" : "text-zinc-300 hover:bg-white/10 hover:text-white"}`}>
                <Icon size={18} />
                {item.label}
              </button>
            );
          })}
        </nav>
      </aside>

      <div className={sidebarOpen ? "lg:ml-72" : ""}>
        <header className="sticky top-0 z-10 flex min-h-16 items-center justify-between border-b border-zinc-200 bg-white px-4 sm:px-6">
          <div className="flex items-center gap-3">
            <button type="button" aria-label="Toggle sidebar" title={sidebarOpen ? "Collapse navigation" : "Open navigation"} className="grid h-10 w-10 place-items-center rounded-md text-zinc-700 hover:bg-zinc-100" onClick={() => setSidebarOpen(!sidebarOpen)}>
              <Menu size={22} />
            </button>
            <div>
              <h1 className="text-lg font-black sm:text-xl">{current}</h1>
              <p className="hidden text-sm text-zinc-500 sm:block">{descriptions[page]}</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="hidden items-center gap-2 rounded-md border border-zinc-200 px-3 py-2 text-sm font-semibold text-zinc-600 sm:flex">
              <BarChart3 size={16} />
              Results Roofing Demo
            </div>
            <div className="h-9 w-9 rounded-full bg-zinc-950 text-center text-sm font-black leading-9 text-white">MF</div>
          </div>
        </header>

        <main className="px-4 py-6 sm:px-6">{children}</main>

        <nav className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-7 border-t border-zinc-200 bg-white lg:hidden">
          {nav.map((item) => {
            const Icon = item.icon;
            const active = item.id === page;
            return (
              <button key={item.id} onClick={() => navigate(item.id)} className={`grid min-h-14 place-items-center text-xs ${active ? "text-command-red" : "text-zinc-500"}`} title={item.label}>
                <Icon size={20} />
              </button>
            );
          })}
        </nav>
      </div>
    </div>
  );
}
