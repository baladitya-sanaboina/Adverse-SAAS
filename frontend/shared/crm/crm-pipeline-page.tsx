"use client";

import { useCallback, useEffect, useMemo, useState, type DragEvent, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  BadgeIndianRupee,
  BriefcaseBusiness,
  Building2,
  CircleDollarSign,
  Columns3,
  ContactRound,
  Filter,
  GripVertical,
  List,
  LoaderCircle,
  Mail,
  MoveRight,
  Phone,
  Plus,
  RefreshCw,
  Search,
  Sparkles,
  UserRound,
} from "lucide-react";
import { DashboardHero } from "@/components/dashboard/dashboard-hero";
import { CrudActionButtons } from "@/components/foundation/crud-action-buttons";
import { LooplessDate } from "@/components/foundation/loopless-date";
import { LooplessSelect } from "@/components/foundation/loopless-select";
import type { CurrentUser } from "@/lib/auth/types";
import type {
  CrmInitialEntity,
  CrmOptions,
  Lead,
  LeadSource,
  LeadStatus,
  Opportunity,
  OpportunityStage,
  Paged,
} from "./types";
import "@loopless-shared/styles/crm-pipeline.css";

type WorkspaceView = "pipeline" | "leads" | "opportunities";
type PipelineLayout = "board" | "list";
type PipelineColumnKey = "NEW" | "CONTACTED" | "QUALIFIED" | "PROPOSAL" | "NEGOTIATION" | "WON" | "LOST";
type DraggedPipelineRecord = { kind: "lead"; id: string } | { kind: "opportunity"; id: string };
type EditorMode =
  | "browse"
  | "lead-create"
  | "lead-view"
  | "lead-edit"
  | "opportunity-create"
  | "opportunity-view"
  | "opportunity-edit";
type LeadForm = {
  name: string;
  company_name: string;
  email: string;
  phone: string;
  source: LeadSource;
  status: LeadStatus;
  owner_id: string;
  client_id: string;
  notes: string;
};
type OpportunityForm = {
  name: string;
  description: string;
  value: string;
  currency: string;
  stage: OpportunityStage;
  owner_id: string;
  client_id: string;
  lead_id: string;
  expected_close_date: string;
};

const leadStatuses: LeadStatus[] = ["NEW", "CONTACTED", "QUALIFIED", "LOST", "CONVERTED"];
const leadPipelineStatuses: LeadStatus[] = ["NEW", "CONTACTED", "QUALIFIED", "LOST"];
const leadSources: LeadSource[] = ["WEBSITE", "REFERRAL", "EMAIL", "PHONE", "SOCIAL", "OTHER"];
const opportunityStages: OpportunityStage[] = ["NEW", "QUALIFIED", "PROPOSAL", "NEGOTIATION", "WON", "LOST"];
const leadPipelineTargets = new Set<PipelineColumnKey>(["NEW", "CONTACTED", "QUALIFIED", "LOST"]);
const opportunityPipelineTargets = new Set<PipelineColumnKey>([
  "NEW",
  "QUALIFIED",
  "PROPOSAL",
  "NEGOTIATION",
  "WON",
  "LOST",
]);
const emptyLead: LeadForm = {
  name: "",
  company_name: "",
  email: "",
  phone: "",
  source: "OTHER",
  status: "NEW",
  owner_id: "",
  client_id: "",
  notes: "",
};
const emptyOpportunity: OpportunityForm = {
  name: "",
  description: "",
  value: "",
  currency: "INR",
  stage: "PROPOSAL",
  owner_id: "",
  client_id: "",
  lead_id: "",
  expected_close_date: "",
};

function titleCase(value: string) {
  return value
    .toLowerCase()
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function responseMessage(value: unknown, fallback: string) {
  if (value && typeof value === "object" && "detail" in value) {
    const detail = (value as { detail?: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail[0] && typeof detail[0] === "object" && "msg" in detail[0]) {
      return String((detail[0] as { msg: unknown }).msg).replace(/^Value error, /, "");
    }
  }
  return fallback;
}

async function jsonRequest<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, { cache: "no-store", ...init });
  const data: unknown = await response.json().catch(() => null);
  if (!response.ok) throw new Error(responseMessage(data, "Unable to complete this request."));
  return data as T;
}

function Field({
  label,
  error,
  wide = false,
  children,
}: {
  label: string;
  error?: string;
  wide?: boolean;
  children: ReactNode;
}) {
  return (
    <label className={`management-field${wide ? " wide" : ""}`}>
      <span>{label}</span>
      {children}
      {error && <small>{error}</small>}
    </label>
  );
}

function InputShell({ icon, children }: { icon: ReactNode; children: ReactNode }) {
  return (
    <span className="management-input">
      {icon}
      {children}
    </span>
  );
}

function PermissionDenied({ message }: { message: string }) {
  return (
    <div className="crm-state crm-error-state">
      <BriefcaseBusiness />
      <strong>CRM access unavailable</strong>
      <span>{message}</span>
    </div>
  );
}

export function CrmPipelinePage({ initialEntity }: { initialEntity?: CrmInitialEntity }) {
  const router = useRouter();
  const [view, setView] = useState<WorkspaceView>("pipeline");
  const [pipelineLayout, setPipelineLayout] = useState<PipelineLayout>("board");
  const [mode, setMode] = useState<EditorMode>(
    initialEntity?.type === "lead"
      ? "lead-view"
      : initialEntity?.type === "opportunity"
        ? "opportunity-view"
        : "browse",
  );
  const [leads, setLeads] = useState<Paged<Lead> | null>(null);
  const [opportunities, setOpportunities] = useState<Paged<Opportunity> | null>(null);
  const [options, setOptions] = useState<CrmOptions>({ owners: [], clients: [] });
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null);
  const [selectedOpportunity, setSelectedOpportunity] = useState<Opportunity | null>(null);
  const [leadForm, setLeadForm] = useState<LeadForm>(emptyLead);
  const [opportunityForm, setOpportunityForm] = useState<OpportunityForm>(emptyOpportunity);
  const [conversionLead, setConversionLead] = useState<Lead | null>(null);
  const [search, setSearch] = useState("");
  const [owner, setOwner] = useState("");
  const [leadSource, setLeadSource] = useState("");
  const [leadStatus, setLeadStatus] = useState("");
  const [opportunityStage, setOpportunityStage] = useState("");
  const [opportunityStatus, setOpportunityStatus] = useState("");
  const [leadPage, setLeadPage] = useState(1);
  const [opportunityPage, setOpportunityPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [movingId, setMovingId] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [touched, setTouched] = useState<Record<string, boolean>>({});

  const permission = useCallback(
    (action: string) =>
      Boolean(currentUser?.permissions.some((item) => item.module === "CRM" && item.action === action)),
    [currentUser],
  );
  const canView = permission("VIEW");
  const canCreate = permission("CREATE");
  const canEdit = permission("EDIT");

  const ownerOptions = useMemo(
    () => [{ value: "", label: "All owners" }, ...options.owners.map((item) => ({ value: item.id, label: item.name }))],
    [options.owners],
  );
  const buildLeadQuery = useCallback(() => {
    const size = view === "pipeline" ? 100 : 20;
    const params = new URLSearchParams({ page: String(view === "pipeline" ? 1 : leadPage), page_size: String(size) });
    if (search.trim()) params.set("search", search.trim());
    if (owner) params.set("owner_id", owner);
    if (leadSource) params.set("source", leadSource);
    if (leadStatus) params.set("status", leadStatus);
    return params.toString();
  }, [leadPage, leadSource, leadStatus, owner, search, view]);
  const buildOpportunityQuery = useCallback(() => {
    const size = view === "pipeline" ? 100 : 20;
    const params = new URLSearchParams({
      page: String(view === "pipeline" ? 1 : opportunityPage),
      page_size: String(size),
    });
    if (search.trim()) params.set("search", search.trim());
    if (owner) params.set("owner_id", owner);
    if (opportunityStage) params.set("stage", opportunityStage);
    if (opportunityStatus) params.set("status", opportunityStatus);
    return params.toString();
  }, [opportunityPage, opportunityStage, opportunityStatus, owner, search, view]);

  const loadWorkspace = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [leadData, opportunityData, optionData, meData] = await Promise.all([
        jsonRequest<Paged<Lead>>(`/api/company/crm/leads?${buildLeadQuery()}`),
        jsonRequest<Paged<Opportunity>>(`/api/company/crm/opportunities?${buildOpportunityQuery()}`),
        jsonRequest<CrmOptions>("/api/company/crm/options"),
        jsonRequest<CurrentUser>("/api/auth/me"),
      ]);
      setLeads(leadData);
      setOpportunities(opportunityData);
      setOptions(optionData);
      setCurrentUser(meData);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to load CRM data.");
    } finally {
      setLoading(false);
    }
  }, [buildLeadQuery, buildOpportunityQuery]);

  const loadDetail = useCallback(async (entity: CrmInitialEntity) => {
    setLoading(true);
    setError("");
    try {
      const [entityData, optionData, meData, leadData] = await Promise.all([
        entity.type === "lead"
          ? jsonRequest<Lead>(`/api/company/crm/leads/${entity.id}`)
          : jsonRequest<Opportunity>(`/api/company/crm/opportunities/${entity.id}`),
        jsonRequest<CrmOptions>("/api/company/crm/options"),
        jsonRequest<CurrentUser>("/api/auth/me"),
        jsonRequest<Paged<Lead>>("/api/company/crm/leads?page=1&page_size=100"),
      ]);
      setOptions(optionData);
      setCurrentUser(meData);
      setLeads(leadData);
      if (entity.type === "lead") {
        const record = entityData as Lead;
        setSelectedLead(record);
        setLeadForm(leadToForm(record));
      } else {
        const record = entityData as Opportunity;
        setSelectedOpportunity(record);
        setOpportunityForm(opportunityToForm(record));
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to load CRM record.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      if (initialEntity) void loadDetail(initialEntity);
      else void loadWorkspace();
    }, 220);
    return () => window.clearTimeout(timer);
  }, [initialEntity, loadDetail, loadWorkspace]);

  useEffect(() => {
    if (!notice) return;
    const timer = window.setTimeout(() => setNotice(""), 3600);
    return () => window.clearTimeout(timer);
  }, [notice]);

  function leadToForm(record: Lead): LeadForm {
    return {
      name: record.name,
      company_name: record.company_name,
      email: record.email ?? "",
      phone: record.phone ?? "",
      source: record.source,
      status: record.status,
      owner_id: record.owner_id,
      client_id: record.client_id ?? "",
      notes: record.notes,
    };
  }

  function opportunityToForm(record: Opportunity): OpportunityForm {
    return {
      name: record.name,
      description: record.description,
      value: record.value,
      currency: record.currency,
      stage: record.stage,
      owner_id: record.owner_id,
      client_id: record.client_id,
      lead_id: record.lead_id ?? "",
      expected_close_date: record.expected_close_date ?? "",
    };
  }

  function switchView(next: WorkspaceView) {
    if (next !== "leads") {
      setLeadStatus("");
    }
    if (next !== "opportunities") {
      setOpportunityStage("");
      setOpportunityStatus("");
    }
    setView(next);
    setLeadPage(1);
    setOpportunityPage(1);
    setError("");
  }

  function openLeadCreate() {
    setLeadForm({ ...emptyLead, owner_id: options.owners[0]?.id ?? "" });
    setSelectedLead(null);
    setFieldErrors({});
    setTouched({});
    setMode("lead-create");
    setError("");
  }

  function openOpportunityCreate(lead?: Lead, preferredStage: OpportunityStage = "PROPOSAL") {
    setConversionLead(lead ?? null);
    setOpportunityForm({
      ...emptyOpportunity,
      name: lead?.company_name ? `${lead.company_name} opportunity` : "",
      owner_id: lead?.owner_id ?? options.owners[0]?.id ?? "",
      client_id: lead?.client_id ?? "",
      lead_id: lead?.id ?? "",
      stage: preferredStage,
    });
    setSelectedOpportunity(null);
    setFieldErrors({});
    setTouched({});
    setMode("opportunity-create");
    setError("");
  }

  function openLead(record: Lead, edit = false) {
    if (!edit) {
      router.push(`/crm/leads/${record.id}`);
      return;
    }
    setSelectedLead(record);
    setLeadForm(leadToForm(record));
    setFieldErrors({});
    setTouched({});
    setMode("lead-edit");
  }

  function openOpportunity(record: Opportunity, edit = false) {
    if (!edit) {
      router.push(`/crm/opportunities/${record.id}`);
      return;
    }
    setSelectedOpportunity(record);
    setOpportunityForm(opportunityToForm(record));
    setFieldErrors({});
    setTouched({});
    setMode("opportunity-edit");
  }

  function backToPipeline() {
    if (initialEntity) {
      router.push("/crm");
      return;
    }
    setMode("browse");
    setSelectedLead(null);
    setSelectedOpportunity(null);
    setConversionLead(null);
    setError("");
    void loadWorkspace();
  }

  function validateLead(key: keyof LeadForm, value: string) {
    if (key === "name" && value.trim().length < 2) return "Enter at least 2 characters.";
    if (key === "email" && value && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) return "Enter a valid email address.";
    if (key === "phone" && value && !/^\+?[0-9 ()-]{7,24}$/.test(value)) return "Enter a valid phone number.";
    if (key === "owner_id" && !value) return "Select an active owner.";
    if (key === "notes" && value.length > 2000) return "Use no more than 2000 characters.";
    return "";
  }

  function validateOpportunity(key: keyof OpportunityForm, value: string) {
    if (key === "name" && value.trim().length < 2) return "Enter at least 2 characters.";
    if (key === "value" && (value === "" || Number.isNaN(Number(value)) || Number(value) < 0))
      return "Enter a value of zero or more.";
    if (key === "currency" && !/^[A-Za-z]{3}$/.test(value)) return "Use a three-letter currency code.";
    if (key === "owner_id" && !value) return "Select an active owner.";
    if (key === "client_id" && !value) return "Select an active client.";
    if (key === "description" && value.length > 3000) return "Use no more than 3000 characters.";
    return "";
  }

  function updateLeadField(key: keyof LeadForm, value: string) {
    setLeadForm((current) => ({ ...current, [key]: value }));
    if (touched[key]) setFieldErrors((current) => ({ ...current, [key]: validateLead(key, value) }));
  }

  function updateOpportunityField(key: keyof OpportunityForm, value: string) {
    setOpportunityForm((current) => ({ ...current, [key]: value }));
    if (touched[key]) setFieldErrors((current) => ({ ...current, [key]: validateOpportunity(key, value) }));
  }

  function touchLead(key: keyof LeadForm) {
    setTouched((current) => ({ ...current, [key]: true }));
    setFieldErrors((current) => ({ ...current, [key]: validateLead(key, leadForm[key]) }));
  }

  function touchOpportunity(key: keyof OpportunityForm) {
    setTouched((current) => ({ ...current, [key]: true }));
    setFieldErrors((current) => ({ ...current, [key]: validateOpportunity(key, opportunityForm[key]) }));
  }

  async function saveLead(event: React.FormEvent) {
    event.preventDefault();
    const errors = Object.fromEntries(
      (Object.keys(leadForm) as Array<keyof LeadForm>).map((key) => [key, validateLead(key, leadForm[key])]),
    );
    setFieldErrors(errors);
    setTouched(Object.fromEntries(Object.keys(leadForm).map((key) => [key, true])));
    if (Object.values(errors).some(Boolean)) return;
    setSaving(true);
    setError("");
    const editing = mode === "lead-edit" && selectedLead;
    try {
      await jsonRequest<Lead>(editing ? `/api/company/crm/leads/${selectedLead.id}` : "/api/company/crm/leads", {
        method: editing ? "PATCH" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: leadForm.name.trim(),
          company_name: leadForm.company_name.trim(),
          email: leadForm.email.trim() || null,
          phone: leadForm.phone.trim() || null,
          source: leadForm.source,
          status: leadForm.status,
          owner_id: leadForm.owner_id,
          client_id: leadForm.client_id || null,
          notes: leadForm.notes.trim(),
        }),
      });
      setNotice(`Lead ${editing ? "updated" : "created"} successfully.`);
      setMode("browse");
      await loadWorkspace();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to save lead.");
    } finally {
      setSaving(false);
    }
  }

  async function saveOpportunity(event: React.FormEvent) {
    event.preventDefault();
    const errors = Object.fromEntries(
      (Object.keys(opportunityForm) as Array<keyof OpportunityForm>).map((key) => [
        key,
        validateOpportunity(key, opportunityForm[key]),
      ]),
    );
    setFieldErrors(errors);
    setTouched(Object.fromEntries(Object.keys(opportunityForm).map((key) => [key, true])));
    if (Object.values(errors).some(Boolean)) return;
    setSaving(true);
    setError("");
    const editing = mode === "opportunity-edit" && selectedOpportunity;
    try {
      await jsonRequest<Opportunity>(
        editing ? `/api/company/crm/opportunities/${selectedOpportunity.id}` : "/api/company/crm/opportunities",
        {
          method: editing ? "PATCH" : "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name: opportunityForm.name.trim(),
            description: opportunityForm.description.trim(),
            value: opportunityForm.value,
            currency: opportunityForm.currency.toUpperCase(),
            stage: opportunityForm.stage,
            owner_id: opportunityForm.owner_id,
            client_id: opportunityForm.client_id,
            lead_id: opportunityForm.lead_id || null,
            expected_close_date: opportunityForm.expected_close_date || null,
          }),
        },
      );
      if (!editing && conversionLead) {
        await jsonRequest<Lead>(`/api/company/crm/leads/${conversionLead.id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ status: "CONVERTED" }),
        });
      }
      setNotice(
        conversionLead
          ? "Lead converted to an opportunity successfully."
          : `Opportunity ${editing ? "updated" : "created"} successfully.`,
      );
      setConversionLead(null);
      setMode("browse");
      await loadWorkspace();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to save opportunity.");
    } finally {
      setSaving(false);
    }
  }

  async function moveLead(record: Lead, status: string) {
    if (status === record.status) return;
    const previous = leads;
    setMovingId(record.id);
    setError("");
    setLeads((current) =>
      current
        ? {
            ...current,
            items: current.items.map((item) =>
              item.id === record.id ? { ...item, status: status as LeadStatus } : item,
            ),
          }
        : current,
    );
    try {
      const updated = await jsonRequest<Lead>(`/api/company/crm/leads/${record.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      });
      setLeads((current) =>
        current
          ? { ...current, items: current.items.map((item) => (item.id === updated.id ? updated : item)) }
          : current,
      );
      setNotice(`Lead moved to ${titleCase(status)}.`);
    } catch (reason) {
      setLeads((current) =>
        current
          ? { ...current, items: current.items.map((item) => (item.id === record.id ? record : item)) }
          : previous,
      );
      setError(reason instanceof Error ? reason.message : "Unable to update pipeline stage.");
    } finally {
      setMovingId("");
    }
  }

  async function moveOpportunity(record: Opportunity, stage: string) {
    if (stage === record.stage) return;
    const previous = opportunities;
    setMovingId(record.id);
    setError("");
    setOpportunities((current) =>
      current
        ? {
            ...current,
            items: current.items.map((item) =>
              item.id === record.id
                ? {
                    ...item,
                    stage: stage as OpportunityStage,
                    status: ["WON", "LOST"].includes(stage) ? "CLOSED" : "OPEN",
                  }
                : item,
            ),
          }
        : current,
    );
    try {
      const updated = await jsonRequest<Opportunity>(`/api/company/crm/opportunities/${record.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ stage }),
      });
      setOpportunities((current) =>
        current
          ? { ...current, items: current.items.map((item) => (item.id === updated.id ? updated : item)) }
          : current,
      );
      setNotice(`Opportunity moved to ${titleCase(stage)}.`);
    } catch (reason) {
      setOpportunities((current) =>
        current
          ? { ...current, items: current.items.map((item) => (item.id === record.id ? record : item)) }
          : previous,
      );
      setError(reason instanceof Error ? reason.message : "Unable to update pipeline stage.");
    } finally {
      setMovingId("");
    }
  }

  const pipelineValue = useMemo(
    () =>
      (opportunities?.items ?? [])
        .filter((item) => item.status === "OPEN")
        .reduce((total, item) => total + Number(item.value), 0),
    [opportunities?.items],
  );

  if (mode !== "browse") {
    return (
      <>
        <DashboardHero title="" highlight="CRM" description="Manage tenant-scoped leads and opportunities." compact />
        <div className="dash-content crm-page">
          <button type="button" className="crm-back-link" onClick={backToPipeline}>
            <ArrowLeft /> Back to CRM
          </button>
          {error && <div className="crm-banner error">{error}</div>}
          {loading ? (
            <div className="crm-state">
              <LoaderCircle className="crm-spin" /> Loading CRM record…
            </div>
          ) : mode.startsWith("lead") ? (
            selectedLead && mode === "lead-view" ? (
              <LeadDetail
                lead={selectedLead}
                clientName={options.clients.find((item) => item.id === selectedLead.client_id)?.name}
                canEdit={canEdit}
                canCreate={canCreate}
                onEdit={() => setMode("lead-edit")}
                onConvert={() => openOpportunityCreate(selectedLead)}
              />
            ) : (
              <LeadEditor
                mode={mode}
                form={leadForm}
                options={options}
                errors={fieldErrors}
                saving={saving}
                onChange={updateLeadField}
                onBlur={touchLead}
                onCancel={backToPipeline}
                onSubmit={saveLead}
              />
            )
          ) : selectedOpportunity && mode === "opportunity-view" ? (
            <OpportunityDetail
              opportunity={selectedOpportunity}
              canEdit={canEdit}
              onEdit={() => setMode("opportunity-edit")}
            />
          ) : (
            <OpportunityEditor
              mode={mode}
              form={opportunityForm}
              options={options}
              leads={leads?.items ?? (conversionLead ? [conversionLead] : [])}
              errors={fieldErrors}
              saving={saving}
              conversionLead={conversionLead}
              onChange={updateOpportunityField}
              onBlur={touchOpportunity}
              onCancel={backToPipeline}
              onSubmit={saveOpportunity}
            />
          )}
        </div>
      </>
    );
  }

  return (
    <>
      <DashboardHero
        title=""
        highlight="CRM Pipeline"
        description="Move leads from first contact to a closed opportunity."
        compact
      />
      <div className="dash-content crm-page">
        {notice && <div className="crm-banner success">{notice}</div>}
        {error && <div className="crm-banner error">{error}</div>}
        <section className="crm-summary">
          <article>
            <ContactRound />
            <span>Open leads</span>
            <strong>
              {(leads?.items ?? []).filter((item) => !["LOST", "CONVERTED"].includes(item.status)).length}
            </strong>
          </article>
          <article>
            <BriefcaseBusiness />
            <span>Open opportunities</span>
            <strong>{(opportunities?.items ?? []).filter((item) => item.status === "OPEN").length}</strong>
          </article>
          <article>
            <BadgeIndianRupee />
            <span>Pipeline value</span>
            <strong>
              {new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(
                pipelineValue,
              )}
            </strong>
          </article>
        </section>

        <section className="crm-workspace">
          <header className="crm-toolbar">
            <div className="crm-view-tabs" aria-label="CRM views">
              {(["pipeline", "leads", "opportunities"] as WorkspaceView[]).map((item) => (
                <button
                  type="button"
                  className={view === item ? "active" : ""}
                  onClick={() => switchView(item)}
                  key={item}
                >
                  {titleCase(item)}
                </button>
              ))}
            </div>
            {view === "pipeline" && (
              <div className="crm-layout-switch" aria-label="Pipeline layout">
                <span>View</span>
                <button
                  type="button"
                  className={pipelineLayout === "board" ? "active" : ""}
                  aria-pressed={pipelineLayout === "board"}
                  onClick={() => setPipelineLayout("board")}
                >
                  <Columns3 /> Board
                </button>
                <button
                  type="button"
                  className={pipelineLayout === "list" ? "active" : ""}
                  aria-pressed={pipelineLayout === "list"}
                  onClick={() => setPipelineLayout("list")}
                >
                  <List /> List
                </button>
              </div>
            )}
            <div className="crm-create-actions">
              {canCreate && (
                <button type="button" className="management-secondary-action" onClick={() => openOpportunityCreate()}>
                  <Plus /> Opportunity
                </button>
              )}
              {canCreate && (
                <button type="button" className="management-primary-action" onClick={openLeadCreate}>
                  <Plus /> Add lead
                </button>
              )}
            </div>
          </header>

          <div className="crm-filters">
            <label className="crm-search">
              <Search />
              <input
                value={search}
                onChange={(event) => {
                  setSearch(event.target.value);
                  setLeadPage(1);
                  setOpportunityPage(1);
                }}
                placeholder="Search leads, companies, email or opportunities"
                aria-label="Search CRM"
              />
            </label>
            <LooplessSelect
              value={owner}
              options={ownerOptions}
              onValueChange={(value) => {
                setOwner(value);
                setLeadPage(1);
                setOpportunityPage(1);
              }}
              ariaLabel="Filter by owner"
            />
            {view !== "opportunities" && (
              <LooplessSelect
                value={leadSource}
                options={[
                  { value: "", label: "All sources" },
                  ...leadSources.map((item) => ({ value: item, label: titleCase(item) })),
                ]}
                onValueChange={(value) => {
                  setLeadSource(value);
                  setLeadPage(1);
                }}
                ariaLabel="Filter by lead source"
              />
            )}
            {view === "leads" && (
              <LooplessSelect
                value={leadStatus}
                options={[
                  { value: "", label: "All lead statuses" },
                  ...leadStatuses.map((item) => ({ value: item, label: titleCase(item) })),
                ]}
                onValueChange={(value) => {
                  setLeadStatus(value);
                  setLeadPage(1);
                }}
                ariaLabel="Filter by lead status"
              />
            )}
            {view === "opportunities" && (
              <LooplessSelect
                value={opportunityStage}
                options={[
                  { value: "", label: "All stages" },
                  ...opportunityStages.map((item) => ({ value: item, label: titleCase(item) })),
                ]}
                onValueChange={(value) => {
                  setOpportunityStage(value);
                  setOpportunityPage(1);
                }}
                ariaLabel="Filter by opportunity stage"
              />
            )}
            {view === "opportunities" && (
              <LooplessSelect
                value={opportunityStatus}
                options={[
                  { value: "", label: "Open and closed" },
                  { value: "OPEN", label: "Open" },
                  { value: "CLOSED", label: "Closed" },
                ]}
                onValueChange={(value) => {
                  setOpportunityStatus(value);
                  setOpportunityPage(1);
                }}
                ariaLabel="Filter by opportunity status"
              />
            )}
          </div>

          {loading ? (
            <div className="crm-state">
              <LoaderCircle className="crm-spin" /> Loading CRM pipeline…
            </div>
          ) : error && !leads && !opportunities ? (
            <div className="crm-state crm-error-state">
              <BriefcaseBusiness />
              <strong>Unable to load CRM data</strong>
              <span>{error}</span>
              <button type="button" onClick={() => void loadWorkspace()}>
                <RefreshCw /> Retry
              </button>
            </div>
          ) : currentUser && !canView ? (
            <PermissionDenied message="CRM VIEW permission is required." />
          ) : view === "pipeline" && pipelineLayout === "board" ? (
            <PipelineBoard
              leads={leads?.items ?? []}
              opportunities={opportunities?.items ?? []}
              canEdit={canEdit}
              canCreate={canCreate}
              movingId={movingId}
              onLeadOpen={openLead}
              onOpportunityOpen={openOpportunity}
              onLeadMove={moveLead}
              onOpportunityMove={moveOpportunity}
              onConvert={openOpportunityCreate}
              onCreate={openLeadCreate}
            />
          ) : view === "pipeline" ? (
            <PipelineListView
              leads={leads?.items ?? []}
              opportunities={opportunities?.items ?? []}
              canEdit={canEdit}
              movingId={movingId}
              onLeadOpen={openLead}
              onOpportunityOpen={openOpportunity}
              onLeadMove={moveLead}
              onOpportunityMove={moveOpportunity}
            />
          ) : view === "leads" ? (
            <LeadList records={leads} canEdit={canEdit} onOpen={openLead} page={leadPage} setPage={setLeadPage} />
          ) : (
            <OpportunityList
              records={opportunities}
              canEdit={canEdit}
              onOpen={openOpportunity}
              page={opportunityPage}
              setPage={setOpportunityPage}
            />
          )}
        </section>
      </div>
    </>
  );
}

function PipelineBoard({
  leads,
  opportunities,
  canEdit,
  canCreate,
  movingId,
  onLeadOpen,
  onOpportunityOpen,
  onLeadMove,
  onOpportunityMove,
  onConvert,
  onCreate,
}: {
  leads: Lead[];
  opportunities: Opportunity[];
  canEdit: boolean;
  canCreate: boolean;
  movingId: string;
  onLeadOpen: (lead: Lead, edit?: boolean) => void;
  onOpportunityOpen: (item: Opportunity, edit?: boolean) => void;
  onLeadMove: (lead: Lead, status: string) => void;
  onOpportunityMove: (item: Opportunity, stage: string) => void;
  onConvert: (lead: Lead, stage?: OpportunityStage) => void;
  onCreate: () => void;
}) {
  const [dragged, setDragged] = useState<DraggedPipelineRecord | null>(null);
  const [dragOver, setDragOver] = useState<PipelineColumnKey | null>(null);
  const columns: Array<{
    key: PipelineColumnKey;
    label: string;
    leads: Lead[];
    opportunities: Opportunity[];
  }> = [
    {
      key: "NEW",
      label: "New",
      leads: leads.filter((item) => item.status === "NEW"),
      opportunities: opportunities.filter((item) => item.stage === "NEW"),
    },
    {
      key: "CONTACTED",
      label: "Contacted",
      leads: leads.filter((item) => item.status === "CONTACTED"),
      opportunities: [],
    },
    {
      key: "QUALIFIED",
      label: "Qualified",
      leads: leads.filter((item) => item.status === "QUALIFIED"),
      opportunities: opportunities.filter((item) => item.stage === "QUALIFIED"),
    },
    {
      key: "PROPOSAL",
      label: "Proposal",
      leads: [],
      opportunities: opportunities.filter((item) => item.stage === "PROPOSAL"),
    },
    {
      key: "NEGOTIATION",
      label: "Negotiation",
      leads: [],
      opportunities: opportunities.filter((item) => item.stage === "NEGOTIATION"),
    },
    { key: "WON", label: "Won", leads: [], opportunities: opportunities.filter((item) => item.stage === "WON") },
    {
      key: "LOST",
      label: "Lost",
      leads: leads.filter((item) => item.status === "LOST"),
      opportunities: opportunities.filter((item) => item.stage === "LOST"),
    },
  ];

  function canDrop(column: PipelineColumnKey) {
    if (!dragged || !canEdit) return false;
    if (dragged.kind === "opportunity") return opportunityPipelineTargets.has(column);
    const lead = leads.find((item) => item.id === dragged.id);
    return leadPipelineTargets.has(column) || (lead?.status === "QUALIFIED" && column === "PROPOSAL" && canCreate);
  }

  function startDrag(event: DragEvent<HTMLElement>, record: DraggedPipelineRecord) {
    if (!canEdit) return;
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/plain", `${record.kind}:${record.id}`);
    setDragged(record);
  }

  function finishDrag() {
    setDragged(null);
    setDragOver(null);
  }

  function dropRecord(event: DragEvent<HTMLElement>, column: PipelineColumnKey) {
    event.preventDefault();
    if (!dragged || !canDrop(column)) return finishDrag();
    if (dragged.kind === "lead") {
      const lead = leads.find((item) => item.id === dragged.id);
      if (lead) {
        if (column === "PROPOSAL") onConvert(lead, "PROPOSAL");
        else void onLeadMove(lead, column);
      }
    } else {
      const opportunity = opportunities.find((item) => item.id === dragged.id);
      if (opportunity) void onOpportunityMove(opportunity, column);
    }
    finishDrag();
  }
  if (!leads.length && !opportunities.length) {
    return (
      <div className="crm-state crm-empty">
        <Sparkles />
        <strong>No CRM records yet</strong>
        <span>Create your first lead to start the pipeline.</span>
        {canCreate && (
          <button type="button" onClick={onCreate}>
            <Plus /> Add lead
          </button>
        )}
      </div>
    );
  }
  return (
    <div className="crm-pipeline" aria-label="CRM pipeline">
      {columns.map((column) => (
        <section
          className={`crm-column stage-${column.key.toLowerCase()}${dragOver === column.key ? " drop-active" : ""}${dragged && !canDrop(column.key) ? " drop-disabled" : ""}`}
          key={column.key}
          onDragEnter={(event) => {
            if (!canDrop(column.key)) return;
            event.preventDefault();
            setDragOver(column.key);
          }}
          onDragOver={(event) => {
            if (!canDrop(column.key)) return;
            event.preventDefault();
            event.dataTransfer.dropEffect = "move";
          }}
          onDragLeave={(event) => {
            if (!event.currentTarget.contains(event.relatedTarget as Node)) setDragOver(null);
          }}
          onDrop={(event) => dropRecord(event, column.key)}
        >
          <header>
            <div>
              <span /> <strong>{column.label}</strong>
            </div>
            <em>{column.leads.length + column.opportunities.length}</em>
          </header>
          <div>
            {column.leads.map((lead) => (
              <article
                className={`crm-card lead${dragged?.kind === "lead" && dragged.id === lead.id ? " dragging" : ""}${movingId === lead.id ? " updating" : ""}`}
                key={lead.id}
                draggable={canEdit && movingId !== lead.id}
                onDragStart={(event) => startDrag(event, { kind: "lead", id: lead.id })}
                onDragEnd={finishDrag}
              >
                {canEdit && (
                  <div className="crm-drag-handle" aria-hidden="true">
                    {movingId === lead.id ? <LoaderCircle className="crm-spin" /> : <GripVertical />}
                    {movingId === lead.id ? "Updating status" : "Drag to move"}
                  </div>
                )}
                <button type="button" className="crm-card-main" onClick={() => onLeadOpen(lead)}>
                  <span>Lead</span>
                  <strong>{lead.name}</strong>
                  <small>{lead.company_name || lead.email || "No company supplied"}</small>
                  <footer>
                    <span>
                      <UserRound /> {lead.owner_name}
                    </span>
                    <em>{titleCase(lead.source)}</em>
                  </footer>
                </button>
                {canEdit && (
                  <div className="crm-card-stage">
                    <LooplessSelect
                      value={lead.status}
                      options={leadPipelineStatuses.map((item) => ({ value: item, label: titleCase(item) }))}
                      onValueChange={(value) => onLeadMove(lead, value)}
                      ariaLabel={`Move ${lead.name}`}
                      disabled={movingId === lead.id}
                    />
                  </div>
                )}
                {canCreate && lead.status === "QUALIFIED" && (
                  <button type="button" className="crm-convert" onClick={() => onConvert(lead)}>
                    <MoveRight /> Convert
                  </button>
                )}
              </article>
            ))}
            {column.opportunities.map((item) => (
              <article
                className={`crm-card opportunity${dragged?.kind === "opportunity" && dragged.id === item.id ? " dragging" : ""}${movingId === item.id ? " updating" : ""}`}
                key={item.id}
                draggable={canEdit && movingId !== item.id}
                onDragStart={(event) => startDrag(event, { kind: "opportunity", id: item.id })}
                onDragEnd={finishDrag}
              >
                {canEdit && (
                  <div className="crm-drag-handle" aria-hidden="true">
                    {movingId === item.id ? <LoaderCircle className="crm-spin" /> : <GripVertical />}
                    {movingId === item.id ? "Updating stage" : "Drag to move"}
                  </div>
                )}
                <button type="button" className="crm-card-main" onClick={() => onOpportunityOpen(item)}>
                  <span>Opportunity</span>
                  <strong>{item.name}</strong>
                  <small>{item.client_name}</small>
                  <footer>
                    <span>
                      <UserRound /> {item.owner_name}
                    </span>
                    <em>
                      {new Intl.NumberFormat("en-IN", {
                        style: "currency",
                        currency: item.currency,
                        maximumFractionDigits: 0,
                      }).format(Number(item.value))}
                    </em>
                  </footer>
                </button>
                {canEdit && (
                  <div className="crm-card-stage">
                    <LooplessSelect
                      value={item.stage}
                      options={opportunityStages.map((stage) => ({ value: stage, label: titleCase(stage) }))}
                      onValueChange={(value) => onOpportunityMove(item, value)}
                      ariaLabel={`Move ${item.name}`}
                      disabled={movingId === item.id}
                    />
                  </div>
                )}
              </article>
            ))}
            {!column.leads.length && !column.opportunities.length && (
              <p>{dragOver === column.key ? "Drop here to move" : "Nothing in this stage"}</p>
            )}
          </div>
        </section>
      ))}
    </div>
  );
}

function PipelineListView({
  leads,
  opportunities,
  canEdit,
  movingId,
  onLeadOpen,
  onOpportunityOpen,
  onLeadMove,
  onOpportunityMove,
}: {
  leads: Lead[];
  opportunities: Opportunity[];
  canEdit: boolean;
  movingId: string;
  onLeadOpen: (lead: Lead, edit?: boolean) => void;
  onOpportunityOpen: (item: Opportunity, edit?: boolean) => void;
  onLeadMove: (lead: Lead, status: string) => void;
  onOpportunityMove: (item: Opportunity, stage: string) => void;
}) {
  if (!leads.length && !opportunities.length) {
    return (
      <div className="crm-state crm-empty">
        <List />
        <strong>No pipeline records found</strong>
        <span>New leads and opportunities will appear here.</span>
      </div>
    );
  }

  return (
    <div className="crm-table crm-pipeline-list" role="table" aria-label="CRM pipeline list">
      <header>
        <span>Record</span>
        <span>Type</span>
        <span>Account</span>
        <span>Owner</span>
        <span>Value</span>
        <span>Status</span>
        <span>Actions</span>
      </header>
      {leads.map((lead) => (
        <article key={`lead-${lead.id}`}>
          <div>
            <b>{lead.name.slice(0, 2)}</b>
            <span>
              <strong>{lead.name}</strong>
              <small>{lead.email ?? lead.phone ?? "No contact details"}</small>
            </span>
          </div>
          <span className="crm-record-kind lead">Lead</span>
          <span>{lead.company_name || "Not supplied"}</span>
          <span>{lead.owner_name}</span>
          <span>—</span>
          <div className={`crm-inline-status status-${lead.status.toLowerCase()}`}>
            <span />
            <LooplessSelect
              value={lead.status}
              options={(lead.status === "CONVERTED" ? ["CONVERTED"] : leadPipelineStatuses).map((status) => ({
                value: status,
                label: titleCase(status),
              }))}
              onValueChange={(value) => onLeadMove(lead, value)}
              ariaLabel={`Change ${lead.name} status`}
              disabled={!canEdit || movingId === lead.id || lead.status === "CONVERTED"}
            />
          </div>
          <CrudActionButtons
            view={{ label: "View lead", onClick: () => onLeadOpen(lead) }}
            edit={canEdit ? { label: "Edit lead", onClick: () => onLeadOpen(lead, true) } : undefined}
          />
        </article>
      ))}
      {opportunities.map((item) => (
        <article key={`opportunity-${item.id}`}>
          <div>
            <b>{item.name.slice(0, 2)}</b>
            <span>
              <strong>{item.name}</strong>
              <small>{item.expected_close_date ? `Close ${item.expected_close_date}` : "No close date"}</small>
            </span>
          </div>
          <span className="crm-record-kind opportunity">Opportunity</span>
          <span>{item.client_name}</span>
          <span>{item.owner_name}</span>
          <span>
            {new Intl.NumberFormat("en-IN", {
              style: "currency",
              currency: item.currency,
              maximumFractionDigits: 0,
            }).format(Number(item.value))}
          </span>
          <div className={`crm-inline-status status-${item.stage.toLowerCase()}`}>
            <span />
            <LooplessSelect
              value={item.stage}
              options={opportunityStages.map((stage) => ({ value: stage, label: titleCase(stage) }))}
              onValueChange={(value) => onOpportunityMove(item, value)}
              ariaLabel={`Change ${item.name} stage`}
              disabled={!canEdit || movingId === item.id}
            />
          </div>
          <CrudActionButtons
            view={{ label: "View opportunity", onClick: () => onOpportunityOpen(item) }}
            edit={canEdit ? { label: "Edit opportunity", onClick: () => onOpportunityOpen(item, true) } : undefined}
          />
        </article>
      ))}
    </div>
  );
}

function LeadList({
  records,
  canEdit,
  onOpen,
  page,
  setPage,
}: {
  records: Paged<Lead> | null;
  canEdit: boolean;
  onOpen: (lead: Lead, edit?: boolean) => void;
  page: number;
  setPage: (page: number) => void;
}) {
  if (!records?.items.length)
    return (
      <div className="crm-state crm-empty">
        <ContactRound />
        <strong>No leads found</strong>
        <span>Try changing your search or filters.</span>
      </div>
    );
  return (
    <>
      <div className="crm-table lead-table" role="table">
        <header>
          <span>Lead</span>
          <span>Company</span>
          <span>Owner</span>
          <span>Source</span>
          <span>Status</span>
          <span>Actions</span>
        </header>
        {records.items.map((lead) => (
          <article key={lead.id}>
            <div>
              <b>{lead.name.slice(0, 2)}</b>
              <span>
                <strong>{lead.name}</strong>
                <small>{lead.email ?? lead.phone ?? "No contact details"}</small>
              </span>
            </div>
            <span>{lead.company_name || "Not supplied"}</span>
            <span>{lead.owner_name}</span>
            <span>{titleCase(lead.source)}</span>
            <em className={lead.status.toLowerCase()}>{titleCase(lead.status)}</em>
            <CrudActionButtons
              view={{ label: "View lead", onClick: () => onOpen(lead) }}
              edit={canEdit ? { label: "Edit lead", onClick: () => onOpen(lead, true) } : undefined}
            />
          </article>
        ))}
      </div>
      <Pagination page={page} totalPages={records.total_pages} total={records.total} label="leads" setPage={setPage} />
    </>
  );
}

function OpportunityList({
  records,
  canEdit,
  onOpen,
  page,
  setPage,
}: {
  records: Paged<Opportunity> | null;
  canEdit: boolean;
  onOpen: (item: Opportunity, edit?: boolean) => void;
  page: number;
  setPage: (page: number) => void;
}) {
  if (!records?.items.length)
    return (
      <div className="crm-state crm-empty">
        <BriefcaseBusiness />
        <strong>No opportunities found</strong>
        <span>Qualify a lead or create an opportunity.</span>
      </div>
    );
  return (
    <>
      <div className="crm-table opportunity-table" role="table">
        <header>
          <span>Opportunity</span>
          <span>Client</span>
          <span>Owner</span>
          <span>Value</span>
          <span>Stage</span>
          <span>Actions</span>
        </header>
        {records.items.map((item) => (
          <article key={item.id}>
            <div>
              <b>{item.name.slice(0, 2)}</b>
              <span>
                <strong>{item.name}</strong>
                <small>
                  {item.expected_close_date
                    ? `Close ${new Date(`${item.expected_close_date}T00:00:00`).toLocaleDateString("en-IN")}`
                    : "No close date"}
                </small>
              </span>
            </div>
            <span>{item.client_name}</span>
            <span>{item.owner_name}</span>
            <span>
              {new Intl.NumberFormat("en-IN", {
                style: "currency",
                currency: item.currency,
                maximumFractionDigits: 0,
              }).format(Number(item.value))}
            </span>
            <em className={item.stage.toLowerCase()}>{titleCase(item.stage)}</em>
            <CrudActionButtons
              view={{ label: "View opportunity", onClick: () => onOpen(item) }}
              edit={canEdit ? { label: "Edit opportunity", onClick: () => onOpen(item, true) } : undefined}
            />
          </article>
        ))}
      </div>
      <Pagination
        page={page}
        totalPages={records.total_pages}
        total={records.total}
        label="opportunities"
        setPage={setPage}
      />
    </>
  );
}

function Pagination({
  page,
  totalPages,
  total,
  label,
  setPage,
}: {
  page: number;
  totalPages: number;
  total: number;
  label: string;
  setPage: (page: number) => void;
}) {
  return (
    <div className="crm-pagination">
      <span>
        Page {page} of {Math.max(totalPages, 1)} · {total} {label}
      </span>
      <div>
        <button type="button" disabled={page <= 1} onClick={() => setPage(page - 1)}>
          Previous
        </button>
        <button type="button" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>
          Next
        </button>
      </div>
    </div>
  );
}

function LeadEditor({
  mode,
  form,
  options,
  errors,
  saving,
  onChange,
  onBlur,
  onCancel,
  onSubmit,
}: {
  mode: EditorMode;
  form: LeadForm;
  options: CrmOptions;
  errors: Record<string, string>;
  saving: boolean;
  onChange: (key: keyof LeadForm, value: string) => void;
  onBlur: (key: keyof LeadForm) => void;
  onCancel: () => void;
  onSubmit: (event: React.FormEvent) => void;
}) {
  const editing = mode === "lead-edit";
  return (
    <section className="management-editor">
      <header>
        <i>
          <ContactRound />
        </i>
        <div>
          <span>{editing ? "Lead update" : "New lead"}</span>
          <h2>{editing ? "Edit lead" : "Create lead"}</h2>
          <p>Capture contact, ownership and tenant-safe Client context.</p>
        </div>
      </header>
      <form className="management-form" onSubmit={onSubmit} noValidate>
        <Field label="Lead name" error={errors.name}>
          <InputShell icon={<UserRound />}>
            <input
              value={form.name}
              onChange={(e) => onChange("name", e.target.value)}
              onBlur={() => onBlur("name")}
              aria-invalid={Boolean(errors.name)}
            />
          </InputShell>
        </Field>
        <Field label="Company">
          <InputShell icon={<Building2 />}>
            <input value={form.company_name} onChange={(e) => onChange("company_name", e.target.value)} />
          </InputShell>
        </Field>
        <Field label="Email" error={errors.email}>
          <InputShell icon={<Mail />}>
            <input
              type="email"
              value={form.email}
              onChange={(e) => onChange("email", e.target.value)}
              onBlur={() => onBlur("email")}
              aria-invalid={Boolean(errors.email)}
            />
          </InputShell>
        </Field>
        <Field label="Phone" error={errors.phone}>
          <InputShell icon={<Phone />}>
            <input
              value={form.phone}
              onChange={(e) => onChange("phone", e.target.value)}
              onBlur={() => onBlur("phone")}
              aria-invalid={Boolean(errors.phone)}
            />
          </InputShell>
        </Field>
        <Field label="Source">
          <LooplessSelect
            value={form.source}
            options={leadSources.map((item) => ({ value: item, label: titleCase(item) }))}
            onValueChange={(value) => onChange("source", value)}
            ariaLabel="Lead source"
          />
        </Field>
        <Field label="Status">
          <LooplessSelect
            value={form.status}
            options={leadStatuses.map((item) => ({ value: item, label: titleCase(item) }))}
            onValueChange={(value) => onChange("status", value)}
            ariaLabel="Lead status"
          />
        </Field>
        <Field label="Owner" error={errors.owner_id}>
          <LooplessSelect
            value={form.owner_id}
            options={[
              { value: "", label: "Select owner" },
              ...options.owners.map((item) => ({ value: item.id, label: item.name })),
            ]}
            onValueChange={(value) => onChange("owner_id", value)}
            ariaLabel="Lead owner"
          />
        </Field>
        <Field label="Linked client">
          <LooplessSelect
            value={form.client_id}
            options={[
              { value: "", label: "No linked client" },
              ...options.clients.map((item) => ({ value: item.id, label: item.name })),
            ]}
            onValueChange={(value) => onChange("client_id", value)}
            ariaLabel="Linked client"
          />
        </Field>
        <Field label="Notes" wide error={errors.notes}>
          <InputShell icon={<Filter />}>
            <textarea
              value={form.notes}
              onChange={(e) => onChange("notes", e.target.value)}
              onBlur={() => onBlur("notes")}
              aria-invalid={Boolean(errors.notes)}
            />
          </InputShell>
        </Field>
        <div className="management-form-footer">
          <button type="button" className="management-secondary-action" onClick={onCancel}>
            Cancel
          </button>
          <button type="submit" className="management-primary-action" disabled={saving}>
            {saving ? <LoaderCircle className="crm-spin" /> : <ContactRound />}{" "}
            {saving ? "Saving…" : editing ? "Update lead" : "Create lead"}
          </button>
        </div>
      </form>
    </section>
  );
}

function OpportunityEditor({
  mode,
  form,
  options,
  leads,
  errors,
  saving,
  conversionLead,
  onChange,
  onBlur,
  onCancel,
  onSubmit,
}: {
  mode: EditorMode;
  form: OpportunityForm;
  options: CrmOptions;
  leads: Lead[];
  errors: Record<string, string>;
  saving: boolean;
  conversionLead: Lead | null;
  onChange: (key: keyof OpportunityForm, value: string) => void;
  onBlur: (key: keyof OpportunityForm) => void;
  onCancel: () => void;
  onSubmit: (event: React.FormEvent) => void;
}) {
  const editing = mode === "opportunity-edit";
  return (
    <section className="management-editor">
      <header>
        <i>
          <BriefcaseBusiness />
        </i>
        <div>
          <span>{conversionLead ? "Lead conversion" : editing ? "Opportunity update" : "New opportunity"}</span>
          <h2>
            {conversionLead ? `Convert ${conversionLead.name}` : editing ? "Edit opportunity" : "Create opportunity"}
          </h2>
          <p>
            {conversionLead && !conversionLead.client_id
              ? "Select an existing Client below to complete this conversion."
              : "Manage value, ownership, Client relationship and pipeline stage."}
          </p>
        </div>
      </header>
      <form className="management-form" onSubmit={onSubmit} noValidate>
        <Field label="Opportunity name" error={errors.name}>
          <InputShell icon={<BriefcaseBusiness />}>
            <input
              value={form.name}
              onChange={(e) => onChange("name", e.target.value)}
              onBlur={() => onBlur("name")}
              aria-invalid={Boolean(errors.name)}
            />
          </InputShell>
        </Field>
        <Field label="Value" error={errors.value}>
          <InputShell icon={<CircleDollarSign />}>
            <input
              type="number"
              min="0"
              step="0.01"
              value={form.value}
              onChange={(e) => onChange("value", e.target.value)}
              onBlur={() => onBlur("value")}
              aria-invalid={Boolean(errors.value)}
            />
          </InputShell>
        </Field>
        <Field label="Currency" error={errors.currency}>
          <InputShell icon={<BadgeIndianRupee />}>
            <input
              maxLength={3}
              value={form.currency}
              onChange={(e) => onChange("currency", e.target.value.toUpperCase())}
              onBlur={() => onBlur("currency")}
              aria-invalid={Boolean(errors.currency)}
            />
          </InputShell>
        </Field>
        <Field label="Stage">
          <LooplessSelect
            value={form.stage}
            options={opportunityStages.map((item) => ({ value: item, label: titleCase(item) }))}
            onValueChange={(value) => onChange("stage", value)}
            ariaLabel="Opportunity stage"
          />
        </Field>
        <Field label="Client" error={errors.client_id}>
          <LooplessSelect
            value={form.client_id}
            options={[
              { value: "", label: "Select client" },
              ...options.clients.map((item) => ({ value: item.id, label: item.name })),
            ]}
            onValueChange={(value) => onChange("client_id", value)}
            ariaLabel="Opportunity client"
            disabled={Boolean(conversionLead?.client_id)}
          />
        </Field>
        <Field label="Owner" error={errors.owner_id}>
          <LooplessSelect
            value={form.owner_id}
            options={[
              { value: "", label: "Select owner" },
              ...options.owners.map((item) => ({ value: item.id, label: item.name })),
            ]}
            onValueChange={(value) => onChange("owner_id", value)}
            ariaLabel="Opportunity owner"
          />
        </Field>
        <Field label="Originating lead">
          <LooplessSelect
            value={form.lead_id}
            options={[
              { value: "", label: "No originating lead" },
              ...leads.map((item) => ({ value: item.id, label: item.name })),
            ]}
            onValueChange={(value) => onChange("lead_id", value)}
            ariaLabel="Originating lead"
            disabled={Boolean(conversionLead)}
          />
        </Field>
        <Field label="Expected close">
          <LooplessDate
            value={form.expected_close_date}
            onValueChange={(value) => onChange("expected_close_date", value)}
            ariaLabel="Expected close"
          />
        </Field>
        <Field label="Description" wide error={errors.description}>
          <InputShell icon={<Filter />}>
            <textarea
              value={form.description}
              onChange={(e) => onChange("description", e.target.value)}
              onBlur={() => onBlur("description")}
              aria-invalid={Boolean(errors.description)}
            />
          </InputShell>
        </Field>
        <div className="management-form-footer">
          <button type="button" className="management-secondary-action" onClick={onCancel}>
            Cancel
          </button>
          <button type="submit" className="management-primary-action" disabled={saving}>
            {saving ? <LoaderCircle className="crm-spin" /> : <BriefcaseBusiness />}{" "}
            {saving
              ? "Saving…"
              : conversionLead
                ? "Convert lead"
                : editing
                  ? "Update opportunity"
                  : "Create opportunity"}
          </button>
        </div>
      </form>
    </section>
  );
}

function LeadDetail({
  lead,
  clientName,
  canEdit,
  canCreate,
  onEdit,
  onConvert,
}: {
  lead: Lead;
  clientName?: string;
  canEdit: boolean;
  canCreate: boolean;
  onEdit: () => void;
  onConvert: () => void;
}) {
  return (
    <section className="management-editor crm-detail">
      <header>
        <i>
          <ContactRound />
        </i>
        <div>
          <span>Lead · {titleCase(lead.status)}</span>
          <h2>{lead.name}</h2>
          <p>{lead.company_name || "Company not supplied"}</p>
        </div>
        <div className="crm-detail-actions">
          {canCreate && lead.status === "QUALIFIED" && (
            <button type="button" className="management-secondary-action" onClick={onConvert}>
              <MoveRight /> Convert
            </button>
          )}
          {canEdit && (
            <button type="button" className="management-primary-action" onClick={onEdit}>
              Edit lead
            </button>
          )}
        </div>
      </header>
      <div className="crm-detail-grid">
        <article>
          <span>Email</span>
          <strong>{lead.email ?? "Not supplied"}</strong>
        </article>
        <article>
          <span>Phone</span>
          <strong>{lead.phone ?? "Not supplied"}</strong>
        </article>
        <article>
          <span>Owner</span>
          <strong>{lead.owner_name}</strong>
        </article>
        <article>
          <span>Source</span>
          <strong>{titleCase(lead.source)}</strong>
        </article>
        <article>
          <span>Linked client</span>
          <strong>{clientName ?? "Not linked"}</strong>
        </article>
        <article>
          <span>Updated</span>
          <strong>{new Date(lead.updated_at).toLocaleString("en-IN")}</strong>
        </article>
        <article className="wide">
          <span>Notes</span>
          <strong>{lead.notes || "No notes supplied."}</strong>
        </article>
      </div>
    </section>
  );
}

function OpportunityDetail({
  opportunity,
  canEdit,
  onEdit,
}: {
  opportunity: Opportunity;
  canEdit: boolean;
  onEdit: () => void;
}) {
  return (
    <section className="management-editor crm-detail">
      <header>
        <i>
          <BriefcaseBusiness />
        </i>
        <div>
          <span>Opportunity · {titleCase(opportunity.stage)}</span>
          <h2>{opportunity.name}</h2>
          <p>{opportunity.client_name}</p>
        </div>
        {canEdit && (
          <div className="crm-detail-actions">
            <button type="button" className="management-primary-action" onClick={onEdit}>
              Edit opportunity
            </button>
          </div>
        )}
      </header>
      <div className="crm-detail-grid">
        <article>
          <span>Value</span>
          <strong>
            {new Intl.NumberFormat("en-IN", { style: "currency", currency: opportunity.currency }).format(
              Number(opportunity.value),
            )}
          </strong>
        </article>
        <article>
          <span>Owner</span>
          <strong>{opportunity.owner_name}</strong>
        </article>
        <article>
          <span>Status</span>
          <strong>{titleCase(opportunity.status)}</strong>
        </article>
        <article>
          <span>Stage</span>
          <strong>{titleCase(opportunity.stage)}</strong>
        </article>
        <article>
          <span>Expected close</span>
          <strong>
            {opportunity.expected_close_date
              ? new Date(`${opportunity.expected_close_date}T00:00:00`).toLocaleDateString("en-IN", {
                  day: "numeric",
                  month: "long",
                  year: "numeric",
                })
              : "Not scheduled"}
          </strong>
        </article>
        <article>
          <span>Originating lead</span>
          <strong>{opportunity.lead_id ? "Linked" : "Not linked"}</strong>
        </article>
        <article className="wide">
          <span>Description</span>
          <strong>{opportunity.description || "No description supplied."}</strong>
        </article>
      </div>
    </section>
  );
}
