export type LeadStatus =
  | "New"
  | "Contacted"
  | "Inspection Scheduled"
  | "Inspection Completed"
  | "Estimate Sent"
  | "Insurance Pending"
  | "Sold"
  | "Lost"
  | "Completed"
  | "Paid";

export type Lead = {
  id: string;
  name: string;
  phone: string;
  address: string;
  city: string;
  leadSource: string;
  assignedRep: string;
  status: LeadStatus;
  roofAge: number;
  stormRelated: boolean;
  nextFollowUpDate: string;
  lastContactedDate: string;
  estimatedValue: number;
  createdDate: string;
  notes: string;
  timeline: string[];
};

export type Rep = {
  name: string;
  leadsAssigned: number;
  untouched: number;
  overdue: number;
  inspections: number;
  estimates: number;
  sold: number;
  lost: number;
  closeRate: number;
  pipeline: number;
};

export type Campaign = {
  stormDate: string;
  city: string;
  neighborhood: string;
  damageType: string;
  targetHomes: number;
  assignedTeam: string;
  status: "Planning" | "Active" | "Follow-Up" | "Completed";
  leadsGenerated: number;
  jobsSold: number;
  pipeline: number;
  notes: string;
};

export type ContentJob = {
  homeowner: string;
  address: string;
  rep: string;
  jobStatus: string;
  beforePhotos: string;
  damagePhotos: string;
  afterPhotos: string;
  droneFootage: string;
  testimonial: string;
  review: string;
  caption: string;
  posted: string;
  driveUrl: string;
  notes: string;
};

export const leadStatuses: LeadStatus[] = [
  "New",
  "Contacted",
  "Inspection Scheduled",
  "Inspection Completed",
  "Estimate Sent",
  "Insurance Pending",
  "Sold",
  "Lost",
  "Completed",
  "Paid",
];

export const reps = ["Mia Carter", "Luis Romero", "Ava Brooks", "Derek Stone", "Nina Patel"];
export const leadSources = ["Storm Door Knock", "Google Local", "Yard Sign", "Referral", "Facebook Ad", "Realtor Partner"];

export const leads: Lead[] = [
  {
    id: "lead-001",
    name: "Rachel Bennett",
    phone: "(214) 555-0186",
    address: "418 Maple Ridge Dr",
    city: "Frisco",
    leadSource: "Storm Door Knock",
    assignedRep: "Mia Carter",
    status: "Estimate Sent",
    roofAge: 14,
    stormRelated: true,
    nextFollowUpDate: "2026-06-29",
    lastContactedDate: "2026-06-24",
    estimatedValue: 23400,
    createdDate: "2026-06-18",
    notes: "Hail bruising on west slope and soft metals marked during inspection. Homeowner wants a clear insurance next-step before approving the build.",
    timeline: ["Lead created", "Rep assigned", "First call completed", "Inspection scheduled", "Estimate sent", "Follow-up overdue"],
  },
  {
    id: "lead-002",
    name: "Marcus Hill",
    phone: "(469) 555-0132",
    address: "9009 Bent Oak Ln",
    city: "Plano",
    leadSource: "Google Local",
    assignedRep: "Luis Romero",
    status: "Inspection Scheduled",
    roofAge: 19,
    stormRelated: false,
    nextFollowUpDate: "2026-07-03",
    lastContactedDate: "2026-06-30",
    estimatedValue: 18200,
    createdDate: "2026-06-26",
    notes: "Active leak near kitchen vent after heavy rain. Inspection scheduled Friday morning with attic photo request.",
    timeline: ["Lead created", "Rep assigned", "First call completed", "Inspection scheduled"],
  },
  {
    id: "lead-003",
    name: "Janelle Ortiz",
    phone: "(972) 555-0199",
    address: "1220 Cottonwood Ct",
    city: "Allen",
    leadSource: "Referral",
    assignedRep: "Ava Brooks",
    status: "Sold",
    roofAge: 16,
    stormRelated: true,
    nextFollowUpDate: "2026-07-08",
    lastContactedDate: "2026-06-28",
    estimatedValue: 27150,
    createdDate: "2026-06-12",
    notes: "HOA color approved and material preference confirmed. Production packet is ready after deductible conversation.",
    timeline: ["Lead created", "Rep assigned", "Inspection completed", "Estimate sent", "Agreement signed"],
  },
  {
    id: "lead-004",
    name: "Anthony Reed",
    phone: "(817) 555-0105",
    address: "7301 Lakeview Terrace",
    city: "McKinney",
    leadSource: "Facebook Ad",
    assignedRep: "Derek Stone",
    status: "New",
    roofAge: 11,
    stormRelated: true,
    nextFollowUpDate: "2026-06-28",
    lastContactedDate: "2026-06-26",
    estimatedValue: 20500,
    createdDate: "2026-06-25",
    notes: "Submitted form after the late-June hail cell. Needs first live conversation and inspection booking.",
    timeline: ["Lead created", "Rep assigned", "Follow-up overdue"],
  },
  {
    id: "lead-005",
    name: "Priya Shah",
    phone: "(214) 555-0164",
    address: "611 Meadow Glen Way",
    city: "Prosper",
    leadSource: "Yard Sign",
    assignedRep: "Nina Patel",
    status: "Insurance Pending",
    roofAge: 22,
    stormRelated: true,
    nextFollowUpDate: "2026-07-02",
    lastContactedDate: "2026-06-27",
    estimatedValue: 31200,
    createdDate: "2026-06-20",
    notes: "Adjuster meeting completed with missing line items flagged. Waiting on revised scope before production handoff.",
    timeline: ["Lead created", "Rep assigned", "Inspection completed", "Estimate sent"],
  },
  {
    id: "lead-006",
    name: "Caleb Nguyen",
    phone: "(682) 555-0117",
    address: "84 Briar Hollow Rd",
    city: "Grapevine",
    leadSource: "Realtor Partner",
    assignedRep: "Mia Carter",
    status: "Completed",
    roofAge: 18,
    stormRelated: false,
    nextFollowUpDate: "2026-07-10",
    lastContactedDate: "2026-06-29",
    estimatedValue: 19850,
    createdDate: "2026-06-02",
    notes: "Install complete with clean yard check. Needs review request, after photos, and final content follow-up.",
    timeline: ["Lead created", "Rep assigned", "Estimate sent", "Sold", "Job completed"],
  },
];

export const repPerformance: Rep[] = [
  { name: "Mia Carter", leadsAssigned: 24, untouched: 2, overdue: 3, inspections: 8, estimates: 7, sold: 5, lost: 1, closeRate: 42, pipeline: 188500 },
  { name: "Luis Romero", leadsAssigned: 19, untouched: 1, overdue: 0, inspections: 6, estimates: 5, sold: 3, lost: 2, closeRate: 30, pipeline: 142800 },
  { name: "Ava Brooks", leadsAssigned: 21, untouched: 0, overdue: 1, inspections: 9, estimates: 8, sold: 6, lost: 1, closeRate: 50, pipeline: 201200 },
  { name: "Derek Stone", leadsAssigned: 17, untouched: 4, overdue: 5, inspections: 4, estimates: 3, sold: 2, lost: 3, closeRate: 22, pipeline: 96500 },
  { name: "Nina Patel", leadsAssigned: 15, untouched: 1, overdue: 1, inspections: 5, estimates: 4, sold: 3, lost: 1, closeRate: 38, pipeline: 121900 },
];

export const stormCampaigns: Campaign[] = [
  { stormDate: "2026-06-16", city: "Frisco", neighborhood: "The Trails", damageType: "Hail and wind", targetHomes: 520, assignedTeam: "Team Red", status: "Active", leadsGenerated: 38, jobsSold: 9, pipeline: 246000, notes: "Strong response west of Teel. Prioritize second touches and adjuster-ready homeowners." },
  { stormDate: "2026-06-21", city: "Allen", neighborhood: "Twin Creeks", damageType: "Hail", targetHomes: 410, assignedTeam: "Team North", status: "Follow-Up", leadsGenerated: 27, jobsSold: 6, pipeline: 168000, notes: "Prioritize second touches and adjuster meetings." },
  { stormDate: "2026-06-27", city: "Plano", neighborhood: "Preston Meadow", damageType: "Wind", targetHomes: 290, assignedTeam: "Team East", status: "Planning", leadsGenerated: 5, jobsSold: 0, pipeline: 42000, notes: "Print route cards before Saturday canvass." },
  { stormDate: "2026-05-30", city: "McKinney", neighborhood: "Stonebridge Ranch", damageType: "Hail", targetHomes: 620, assignedTeam: "Team West", status: "Completed", leadsGenerated: 61, jobsSold: 18, pipeline: 386000, notes: "Campaign closed; content follow-ups remain." },
];

export const contentJobs: ContentJob[] = [
  { homeowner: "Caleb Nguyen", address: "84 Briar Hollow Rd", rep: "Mia Carter", jobStatus: "Completed", beforePhotos: "Uploaded", damagePhotos: "Uploaded", afterPhotos: "Needed", droneFootage: "Missing", testimonial: "Requested", review: "Needed", caption: "Needed", posted: "Missing", driveUrl: "drive.google.com/folder-placeholder", notes: "Great candidate for leak-to-finished-roof story and Google review request." },
  { homeowner: "Janelle Ortiz", address: "1220 Cottonwood Ct", rep: "Ava Brooks", jobStatus: "Sold", beforePhotos: "Ready", damagePhotos: "Ready", afterPhotos: "Missing", droneFootage: "Requested", testimonial: "Missing", review: "Missing", caption: "Needed", posted: "Missing", driveUrl: "drive.google.com/folder-placeholder", notes: "Capture material delivery and crew setup." },
  { homeowner: "Rachel Bennett", address: "418 Maple Ridge Dr", rep: "Mia Carter", jobStatus: "Estimate Sent", beforePhotos: "Uploaded", damagePhotos: "Ready", afterPhotos: "Missing", droneFootage: "Missing", testimonial: "Missing", review: "Missing", caption: "Ready", posted: "Missing", driveUrl: "drive.google.com/folder-placeholder", notes: "Storm education caption drafted." },
  { homeowner: "Priya Shah", address: "611 Meadow Glen Way", rep: "Nina Patel", jobStatus: "Insurance Pending", beforePhotos: "Uploaded", damagePhotos: "Uploaded", afterPhotos: "Missing", droneFootage: "Missing", testimonial: "Missing", review: "Missing", caption: "Needed", posted: "Missing", driveUrl: "drive.google.com/folder-placeholder", notes: "Wait for approved scope before publishing." },
];
