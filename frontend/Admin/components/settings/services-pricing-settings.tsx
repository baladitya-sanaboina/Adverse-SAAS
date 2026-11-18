"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { BriefcaseBusiness, CircleDollarSign, Contact, Plus, RefreshCw, Search, UserRound } from "lucide-react";
import { ConfirmationDialog } from "@/components/foundation/confirmation-dialog";
import { CrudActionButtons } from "@/components/foundation/crud-action-buttons";
import { LooplessSelect } from "@/components/foundation/loopless-select";
import { ManagementModal } from "@/components/foundation/management-modal";
import "@/styles/service-pricing-settings.css";

type ServiceStatus = "ACTIVE" | "INACTIVE";
type PricingModeCode = "PER_VIDEO" | "PER_PIECE" | "MONTHLY_FIXED" | "MONTHLY_PACKAGE" | "COMMISSION_PER_DELIVERABLE";
type SubjectTab = "services" | "clients" | "managers";
type MoneyValue = string | number;

type Service = {
  id: string;
  company_id: string;
  name: string;
  code: string;
  description: string;
  client_pricing_model: PricingModeCode;
  manager_pricing_model: PricingModeCode;
  status: ServiceStatus;
  sort_order: number;
  created_at: string;
  updated_at: string;
  active_client_rates: number;
  active_manager_rates: number;
  pricing_history_entries: number;
  safe_to_delete: boolean;
};

type ServiceListResponse = {
  items: Service[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
};

type Client = {
  id: string;
  name: string;
  code: string;
  status: ServiceStatus;
};

type ClientListResponse = {
  items: Client[];
};

type Manager = {
  id: string;
  name: string;
  email: string;
  role_code: string;
  role_name: string;
  status: string;
};

type ManagerListResponse = {
  items: Manager[];
};

type PricingRecord = {
  id: string;
  scope: "CLIENT" | "MANAGER";
  pricing_model: PricingModeCode;
  amount: MoneyValue;
  currency: string;
  notes: string;
  effective_from: string;
  effective_to: string | null;
  created_by_id: string;
  created_by_name: string;
  created_at: string;
};

type PricingItem = {
  service_id: string;
  service_name: string;
  service_code: string;
  service_description: string;
  service_status: ServiceStatus;
  default_pricing_model: PricingModeCode;
  configured: boolean;
  current_rate: PricingRecord | null;
  history_count: number;
  history: PricingRecord[];
};

type PricingOverview = {
  scope: "CLIENT" | "MANAGER";
  subject: { id: string; name: string; subtitle: string };
  items: PricingItem[];
  total_services: number;
  configured_services: number;
  missing_services: number;
};

type ServiceForm = {
  name: string;
  description: string;
  client_pricing_model: PricingModeCode;
  manager_pricing_model: PricingModeCode;
  status: ServiceStatus;
  sort_order: string;
};

type PricingForm = {
  pricing_model: PricingModeCode;
  amount: string;
  effective_date: string;
  notes: string;
};

type PendingServiceAction = { type: "toggle" | "delete"; service: Service } | null;

type ServiceEditorMode = "create" | "edit" | "view" | null;
type PricingEditorMode = "edit" | "view" | null;

const pricingModelOptions = [
  { value: "PER_VIDEO", label: "Per video" },
  { value: "PER_PIECE", label: "Per piece" },
  { value: "MONTHLY_FIXED", label: "Monthly fixed" },
  { value: "MONTHLY_PACKAGE", label: "Monthly package" },
  { value: "COMMISSION_PER_DELIVERABLE", label: "Commission / per deliverable" },
] as const;
const serviceStatusOptions = [
  { value: "", label: "All statuses" },
  { value: "ACTIVE", label: "Active" },
  { value: "INACTIVE", label: "Inactive" },
] as const;
const serviceModes = [
  { value: "services", label: "Services", icon: BriefcaseBusiness },
  { value: "clients", label: "Client pricing", icon: Contact },
  { value: "managers", label: "Manager pricing", icon: CircleDollarSign },
] as const;
const emptyServiceForm: ServiceForm = {
  name: "",
  description: "",
  client_pricing_model: "PER_VIDEO",
  manager_pricing_model: "COMMISSION_PER_DELIVERABLE",
  status: "ACTIVE",
  sort_order: "0",
};
const emptyPricingForm: PricingForm = {
  pricing_model: "PER_VIDEO",
  amount: "",
  effective_date: "",
  notes: "",
};

function messageFrom(value: unknown, fallback: string) {
  if (value && typeof value === "object" && "detail" in value) {
    const detail = (value as { detail?: unknown }).detail;
    if (typeof detail === "string") return detail;
  }
  return fallback;
}

function pricingLabel(value: PricingModeCode) {
  return pricingModelOptions.find((option) => option.value === value)?.label ?? value;
}

function statusLabel(value: ServiceStatus) {
  return value === "ACTIVE" ? "Active" : "Inactive";
}

function formatMoney(amount: MoneyValue | null | undefined, currency: string) {
  if (amount === null || amount === undefined || amount === "") return "Not configured";
  const numeric = Number(amount);
  try {
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: currency || "INR",
      maximumFractionDigits: 2,
    }).format(Number.isFinite(numeric) ? numeric : 0);
  } catch {
    return `${currency || "INR"} ${Number.isFinite(numeric) ? numeric.toFixed(2) : amount}`;
  }
}

function formatDate(value: string | null | undefined) {
  if (!value) return "—";
  return new Date(value).toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function todayInputValue() {
  const current = new Date();
  const year = current.getFullYear();
  const month = `${current.getMonth() + 1}`.padStart(2, "0");
  const day = `${current.getDate()}`.padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function toEffectiveDateIso(value: string) {
  const today = todayInputValue();
  if (!value || value === today) return new Date().toISOString();
  const [year, month, day] = value.split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, day, 0, 0, 0)).toISOString();
}

export function ServicesPricingSettings({ currency }: { currency: string }) {
  const [services, setServices] = useState<Service[]>([]);
  const [clients, setClients] = useState<Client[]>([]);
  const [managers, setManagers] = useState<Manager[]>([]);
  const [activeTab, setActiveTab] = useState<SubjectTab>("services");
  const [loading, setLoading] = useState(true);
  const [pricingLoading, setPricingLoading] = useState(false);
  const [serviceSaving, setServiceSaving] = useState(false);
  const [pricingSaving, setPricingSaving] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [pricingError, setPricingError] = useState("");
  const [serviceSearch, setServiceSearch] = useState("");
  const [serviceStatusFilter, setServiceStatusFilter] = useState("");
  const [pricingSearch, setPricingSearch] = useState("");
  const [selectedClientId, setSelectedClientId] = useState("");
  const [selectedManagerId, setSelectedManagerId] = useState("");
  const [clientPricing, setClientPricing] = useState<PricingOverview | null>(null);
  const [managerPricing, setManagerPricing] = useState<PricingOverview | null>(null);
  const [serviceEditorMode, setServiceEditorMode] = useState<ServiceEditorMode>(null);
  const [selectedService, setSelectedService] = useState<Service | null>(null);
  const [serviceForm, setServiceForm] = useState<ServiceForm>(emptyServiceForm);
  const [serviceFormError, setServiceFormError] = useState("");
  const [pendingServiceAction, setPendingServiceAction] = useState<PendingServiceAction>(null);
  const [pricingEditorMode, setPricingEditorMode] = useState<PricingEditorMode>(null);
  const [selectedPricingItem, setSelectedPricingItem] = useState<PricingItem | null>(null);
  const [pricingForm, setPricingForm] = useState<PricingForm>(emptyPricingForm);
  const [pricingFormError, setPricingFormError] = useState("");

  useEffect(() => {
    if (!notice) return;
    const timer = window.setTimeout(() => setNotice(""), 3200);
    return () => window.clearTimeout(timer);
  }, [notice]);

  const loadServices = useCallback(async () => {
    const response = await fetch("/api/company/services?page_size=100", { cache: "no-store" });
    const body = (await response.json()) as ServiceListResponse | { detail?: string };
    if (!response.ok) throw new Error(messageFrom(body, "Unable to load services."));
    setServices("items" in body && Array.isArray(body.items) ? body.items : []);
  }, []);

  const loadClients = useCallback(async () => {
    const response = await fetch("/api/company/clients?page_size=100", { cache: "no-store" });
    const body = (await response.json()) as ClientListResponse | { detail?: string };
    if (!response.ok) throw new Error(messageFrom(body, "Unable to load clients."));
    const items = ("items" in body && Array.isArray(body.items) ? body.items : []).filter(
      (item: Client) => item.status === "ACTIVE",
    );
    setClients(items);
    setSelectedClientId((current) => current || items[0]?.id || "");
  }, []);

  const loadManagers = useCallback(async () => {
    const response = await fetch("/api/company/users", { cache: "no-store" });
    const body = (await response.json()) as ManagerListResponse | { detail?: string };
    if (!response.ok) throw new Error(messageFrom(body, "Unable to load managers."));
    const items = ("items" in body && Array.isArray(body.items) ? body.items : []).filter(
      (item: Manager) => item.status === "ACTIVE" && item.role_code === "COMPANY_MANAGER",
    );
    setManagers(items);
    setSelectedManagerId((current) => current || items[0]?.id || "");
  }, []);

  const loadSetup = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      await Promise.all([loadServices(), loadClients(), loadManagers()]);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to load service pricing setup.");
    } finally {
      setLoading(false);
    }
  }, [loadClients, loadManagers, loadServices]);

  const loadClientPricing = useCallback(async (clientId: string) => {
    if (!clientId) {
      setClientPricing(null);
      return;
    }
    setPricingLoading(true);
    setPricingError("");
    try {
      const response = await fetch(`/api/company/pricing/clients/${clientId}?include_history=true`, {
        cache: "no-store",
      });
      const body = (await response.json()) as PricingOverview | { detail?: string };
      if (!response.ok) throw new Error(messageFrom(body, "Unable to load client pricing."));
      setClientPricing(body as PricingOverview);
    } catch (reason) {
      setPricingError(reason instanceof Error ? reason.message : "Unable to load client pricing.");
    } finally {
      setPricingLoading(false);
    }
  }, []);

  const loadManagerPricing = useCallback(async (managerId: string) => {
    if (!managerId) {
      setManagerPricing(null);
      return;
    }
    setPricingLoading(true);
    setPricingError("");
    try {
      const response = await fetch(`/api/company/pricing/managers/${managerId}?include_history=true`, {
        cache: "no-store",
      });
      const body = (await response.json()) as PricingOverview | { detail?: string };
      if (!response.ok) throw new Error(messageFrom(body, "Unable to load manager pricing."));
      setManagerPricing(body as PricingOverview);
    } catch (reason) {
      setPricingError(reason instanceof Error ? reason.message : "Unable to load manager pricing.");
    } finally {
      setPricingLoading(false);
    }
  }, []);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      void loadSetup();
    }, 0);
    return () => window.clearTimeout(timeoutId);
  }, [loadSetup]);

  useEffect(() => {
    if (activeTab !== "clients" || !selectedClientId) return;
    const timeoutId = window.setTimeout(() => {
      void loadClientPricing(selectedClientId);
    }, 0);
    return () => window.clearTimeout(timeoutId);
  }, [activeTab, loadClientPricing, selectedClientId]);

  useEffect(() => {
    if (activeTab !== "managers" || !selectedManagerId) return;
    const timeoutId = window.setTimeout(() => {
      void loadManagerPricing(selectedManagerId);
    }, 0);
    return () => window.clearTimeout(timeoutId);
  }, [activeTab, loadManagerPricing, selectedManagerId]);

  const filteredServices = useMemo(() => {
    const query = serviceSearch.trim().toLowerCase();
    return services.filter((service) => {
      const matchesSearch =
        !query ||
        service.name.toLowerCase().includes(query) ||
        service.code.toLowerCase().includes(query) ||
        service.description.toLowerCase().includes(query);
      const matchesStatus = !serviceStatusFilter || service.status === serviceStatusFilter;
      return matchesSearch && matchesStatus;
    });
  }, [serviceSearch, serviceStatusFilter, services]);

  const activePricing = activeTab === "clients" ? clientPricing : managerPricing;
  const filteredPricingItems = useMemo(() => {
    const query = pricingSearch.trim().toLowerCase();
    const items = activePricing?.items ?? [];
    return items.filter((item) => {
      if (!query) return true;
      return (
        item.service_name.toLowerCase().includes(query) ||
        item.service_code.toLowerCase().includes(query) ||
        item.service_description.toLowerCase().includes(query)
      );
    });
  }, [activePricing?.items, pricingSearch]);

  const serviceSummary = useMemo(
    () => ({
      total: services.length,
      active: services.filter((service) => service.status === "ACTIVE").length,
      clientRates: services.reduce((count, service) => count + service.active_client_rates, 0),
      managerRates: services.reduce((count, service) => count + service.active_manager_rates, 0),
    }),
    [services],
  );

  function openServiceEditor(mode: ServiceEditorMode, service?: Service) {
    setSelectedService(service ?? null);
    setServiceEditorMode(mode);
    setServiceFormError("");
    setServiceForm(
      service
        ? {
            name: service.name,
            description: service.description,
            client_pricing_model: service.client_pricing_model,
            manager_pricing_model: service.manager_pricing_model,
            status: service.status,
            sort_order: String(service.sort_order),
          }
        : emptyServiceForm,
    );
  }

  function openPricingEditor(mode: PricingEditorMode, item: PricingItem) {
    setSelectedPricingItem(item);
    setPricingEditorMode(mode);
    setPricingFormError("");
    setPricingForm({
      pricing_model: item.current_rate?.pricing_model ?? item.default_pricing_model,
      amount: item.current_rate ? String(item.current_rate.amount) : "",
      effective_date: todayInputValue(),
      notes: item.current_rate?.notes ?? "",
    });
  }

  async function saveService() {
    if (!serviceForm.name.trim()) {
      setServiceFormError("Service name is required.");
      return;
    }
    setServiceSaving(true);
    setServiceFormError("");
    try {
      const response = await fetch(
        serviceEditorMode === "create" ? "/api/company/services" : `/api/company/services/${selectedService?.id}`,
        {
          method: serviceEditorMode === "create" ? "POST" : "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name: serviceForm.name.trim(),
            description: serviceForm.description.trim(),
            client_pricing_model: serviceForm.client_pricing_model,
            manager_pricing_model: serviceForm.manager_pricing_model,
            status: serviceForm.status,
            sort_order: Number(serviceForm.sort_order || 0),
          }),
        },
      );
      const body = (await response.json()) as Service | { detail?: string };
      if (!response.ok) throw new Error(messageFrom(body, "Unable to save service."));
      await loadServices();
      setServiceEditorMode(null);
      setSelectedService(null);
      setNotice(serviceEditorMode === "create" ? "Service created successfully." : "Service updated successfully.");
    } catch (reason) {
      setServiceFormError(reason instanceof Error ? reason.message : "Unable to save service.");
    } finally {
      setServiceSaving(false);
    }
  }

  async function confirmServiceAction() {
    if (!pendingServiceAction) return;
    setServiceSaving(true);
    setError("");
    try {
      if (pendingServiceAction.type === "toggle") {
        const response = await fetch(`/api/company/services/${pendingServiceAction.service.id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            status: pendingServiceAction.service.status === "ACTIVE" ? "INACTIVE" : "ACTIVE",
          }),
        });
        const body = (await response.json()) as Service | { detail?: string };
        if (!response.ok) throw new Error(messageFrom(body, "Unable to update service status."));
        setNotice(
          pendingServiceAction.service.status === "ACTIVE"
            ? "Service deactivated successfully."
            : "Service activated successfully.",
        );
      } else {
        const response = await fetch(`/api/company/services/${pendingServiceAction.service.id}`, {
          method: "DELETE",
        });
        if (!response.ok) {
          const body = (await response.json()) as { detail?: string };
          throw new Error(messageFrom(body, "Unable to delete service."));
        }
        setNotice("Service deleted successfully.");
      }
      await loadServices();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to complete the service action.");
    } finally {
      setServiceSaving(false);
      setPendingServiceAction(null);
    }
  }

  async function savePricing() {
    if (!selectedPricingItem) return;
    const subjectId = activeTab === "clients" ? selectedClientId : selectedManagerId;
    if (!subjectId) {
      setPricingFormError(activeTab === "clients" ? "Select a client first." : "Select a manager first.");
      return;
    }
    if (!pricingForm.amount || Number.isNaN(Number(pricingForm.amount)) || Number(pricingForm.amount) < 0) {
      setPricingFormError("Enter a valid amount.");
      return;
    }
    setPricingSaving(true);
    setPricingFormError("");
    try {
      const route =
        activeTab === "clients"
          ? `/api/company/pricing/clients/${subjectId}/services/${selectedPricingItem.service_id}`
          : `/api/company/pricing/managers/${subjectId}/services/${selectedPricingItem.service_id}`;
      const response = await fetch(route, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          pricing_model: pricingForm.pricing_model,
          amount: Number(pricingForm.amount).toFixed(2),
          effective_from: toEffectiveDateIso(pricingForm.effective_date),
          notes: pricingForm.notes.trim() || null,
        }),
      });
      const body = (await response.json()) as PricingRecord | { detail?: string };
      if (!response.ok) throw new Error(messageFrom(body, "Unable to save pricing."));
      if (activeTab === "clients") await loadClientPricing(subjectId);
      else await loadManagerPricing(subjectId);
      await loadServices();
      setPricingEditorMode(null);
      setSelectedPricingItem(null);
      setNotice(activeTab === "clients" ? "Client pricing saved successfully." : "Manager pricing saved successfully.");
    } catch (reason) {
      setPricingFormError(reason instanceof Error ? reason.message : "Unable to save pricing.");
    } finally {
      setPricingSaving(false);
    }
  }

  const serviceOptions = useMemo(
    () => [
      { value: "", label: activeTab === "clients" ? "Select client" : "Select manager" },
      ...(activeTab === "clients"
        ? clients.map((client) => ({ value: client.id, label: `${client.name} · ${client.code}` }))
        : managers.map((manager) => ({ value: manager.id, label: `${manager.name} · ${manager.email}` }))),
    ],
    [activeTab, clients, managers],
  );

  return (
    <section className="services-pricing-settings" aria-live="polite">
      <header className="settings-section-title services-pricing-title">
        <div>
          <span>Company settings</span>
          <h3>Services & pricing</h3>
        </div>
        <p>
          Manage the database-driven service catalog plus client and manager pricing history without changing the UI
          shell.
        </p>
      </header>

      <div className="services-pricing-summary-grid">
        <article>
          <span>Service catalog</span>
          <strong>{serviceSummary.total}</strong>
          <small>Total configured services</small>
        </article>
        <article>
          <span>Active services</span>
          <strong>{serviceSummary.active}</strong>
          <small>Available for new pricing and future work</small>
        </article>
        <article>
          <span>Client rates</span>
          <strong>{serviceSummary.clientRates}</strong>
          <small>Open client-specific service rates</small>
        </article>
        <article>
          <span>Manager rates</span>
          <strong>{serviceSummary.managerRates}</strong>
          <small>Open manager payout configurations</small>
        </article>
      </div>

      <nav className="services-pricing-modes" aria-label="Services and pricing controls">
        {serviceModes.map((item) => {
          const Icon = item.icon;
          return (
            <button
              type="button"
              key={item.value}
              className={activeTab === item.value ? "active" : ""}
              onClick={() => {
                setActiveTab(item.value);
                setPricingSearch("");
                setPricingError("");
              }}
            >
              <Icon aria-hidden="true" />
              <strong>{item.label}</strong>
            </button>
          );
        })}
      </nav>

      {notice && <div className="services-pricing-notice">{notice}</div>}
      {error && <div className="services-pricing-error">{error}</div>}

      {activeTab === "services" ? (
        <>
          <div className="management-toolbar">
            <div>
              <span>Service catalog</span>
              <strong>Dynamic service management</strong>
            </div>
            <button type="button" onClick={() => openServiceEditor("create")}>
              <Plus /> Add service
            </button>
          </div>
          <div className="services-pricing-filters">
            <label>
              <Search aria-hidden="true" />
              <input
                value={serviceSearch}
                onChange={(event) => setServiceSearch(event.target.value)}
                placeholder="Search services"
              />
            </label>
            <LooplessSelect
              value={serviceStatusFilter}
              options={serviceStatusOptions}
              onValueChange={setServiceStatusFilter}
              ariaLabel="Filter services by status"
            />
          </div>
          <section className="services-pricing-table" aria-live="polite">
            {loading ? (
              <div className="services-pricing-state">
                <i /> Loading services…
              </div>
            ) : filteredServices.length === 0 ? (
              <div className="services-pricing-state empty">
                <BriefcaseBusiness />
                <strong>No services found</strong>
                <span>Try another filter or create a new service.</span>
              </div>
            ) : (
              <>
                <div className="services-pricing-head" role="row">
                  <span>Service</span>
                  <span>Client model</span>
                  <span>Manager model</span>
                  <span>Status</span>
                  <span>History</span>
                  <span>Action</span>
                </div>
                {filteredServices.map((service) => (
                  <article key={service.id} role="row">
                    <div>
                      <strong>{service.name}</strong>
                      <small>{service.code}</small>
                      <p>{service.description || "No description added yet."}</p>
                    </div>
                    <span>{pricingLabel(service.client_pricing_model)}</span>
                    <span>{pricingLabel(service.manager_pricing_model)}</span>
                    <span>
                      <b className={`services-pricing-pill ${service.status === "ACTIVE" ? "active" : "inactive"}`}>
                        {statusLabel(service.status)}
                      </b>
                    </span>
                    <span>
                      {service.pricing_history_entries} entries
                      <small>
                        {service.active_client_rates} client · {service.active_manager_rates} manager
                      </small>
                    </span>
                    <CrudActionButtons
                      active={service.status === "ACTIVE"}
                      view={{ label: `View ${service.name}`, onClick: () => openServiceEditor("view", service) }}
                      edit={{ label: `Edit ${service.name}`, onClick: () => openServiceEditor("edit", service) }}
                      toggle={{
                        label: service.status === "ACTIVE" ? `Deactivate ${service.name}` : `Activate ${service.name}`,
                        onClick: () => setPendingServiceAction({ type: "toggle", service }),
                      }}
                      remove={{
                        label: `Delete ${service.name}`,
                        onClick: () => setPendingServiceAction({ type: "delete", service }),
                        disabled: !service.safe_to_delete,
                      }}
                    />
                  </article>
                ))}
              </>
            )}
          </section>
        </>
      ) : (
        <>
          <div className="management-toolbar pricing-toolbar">
            <div>
              <span>{activeTab === "clients" ? "Client pricing" : "Manager pricing"}</span>
              <strong>
                {activeTab === "clients" ? "Client-specific billing rates" : "Manager-specific per-service payouts"}
              </strong>
            </div>
            <button
              type="button"
              className="management-back"
              onClick={() =>
                activeTab === "clients"
                  ? void loadClientPricing(selectedClientId)
                  : void loadManagerPricing(selectedManagerId)
              }
            >
              <RefreshCw /> Refresh
            </button>
          </div>
          <div className="services-pricing-filters pricing-filters-grid">
            <div className="services-pricing-selectors">
              <LooplessSelect
                value={activeTab === "clients" ? selectedClientId : selectedManagerId}
                options={serviceOptions}
                onValueChange={(value) => {
                  if (activeTab === "clients") setSelectedClientId(value);
                  else setSelectedManagerId(value);
                }}
                ariaLabel={activeTab === "clients" ? "Select client" : "Select manager"}
              />
            </div>
            <label>
              <Search aria-hidden="true" />
              <input
                value={pricingSearch}
                onChange={(event) => setPricingSearch(event.target.value)}
                placeholder="Search services"
              />
            </label>
          </div>
          {pricingError && <div className="services-pricing-error">{pricingError}</div>}
          {!pricingLoading && !activePricing ? (
            <div className="services-pricing-state empty">
              {activeTab === "clients" ? <Contact /> : <UserRound />}
              <strong>{activeTab === "clients" ? "Select a client" : "Select a manager"}</strong>
              <span>
                {activeTab === "clients"
                  ? "Choose a client to manage service-specific pricing."
                  : "Choose a manager to manage per-service payout rates."}
              </span>
            </div>
          ) : (
            <>
              {activePricing && (
                <div className="services-pricing-subject-card">
                  <div>
                    <span>{activeTab === "clients" ? "Client" : "Manager"}</span>
                    <strong>{activePricing.subject.name}</strong>
                    <small>{activePricing.subject.subtitle}</small>
                  </div>
                  <div>
                    <span>Configured</span>
                    <strong>{activePricing.configured_services}</strong>
                    <small>{activePricing.missing_services} missing</small>
                  </div>
                </div>
              )}
              <section className="services-pricing-table" aria-live="polite">
                {pricingLoading ? (
                  <div className="services-pricing-state">
                    <i /> Loading pricing…
                  </div>
                ) : filteredPricingItems.length === 0 ? (
                  <div className="services-pricing-state empty">
                    <CircleDollarSign />
                    <strong>No pricing rows found</strong>
                    <span>Try another service search or create more services first.</span>
                  </div>
                ) : (
                  <>
                    <div className="services-pricing-head pricing-head" role="row">
                      <span>Service</span>
                      <span>Model</span>
                      <span>Current rate</span>
                      <span>Effective from</span>
                      <span>History</span>
                      <span>Action</span>
                    </div>
                    {filteredPricingItems.map((item) => (
                      <article key={item.service_id} role="row">
                        <div>
                          <strong>{item.service_name}</strong>
                          <small>{item.service_code}</small>
                          <p>{item.service_description || "No description added yet."}</p>
                        </div>
                        <span>{pricingLabel(item.current_rate?.pricing_model ?? item.default_pricing_model)}</span>
                        <span className={item.configured ? "" : "services-pricing-missing"}>
                          {item.configured && item.current_rate
                            ? formatMoney(item.current_rate.amount, item.current_rate.currency)
                            : `Missing · ${currency || "INR"}`}
                        </span>
                        <span>{item.current_rate ? formatDate(item.current_rate.effective_from) : "—"}</span>
                        <span>
                          {item.history_count} entries
                          <small>
                            {item.configured ? `Updated by ${item.current_rate?.created_by_name}` : "Not configured"}
                          </small>
                        </span>
                        <CrudActionButtons
                          view={{
                            label: `View pricing for ${item.service_name}`,
                            onClick: () => openPricingEditor("view", item),
                          }}
                          edit={{
                            label: `Edit pricing for ${item.service_name}`,
                            onClick: () => openPricingEditor("edit", item),
                          }}
                        />
                      </article>
                    ))}
                  </>
                )}
              </section>
            </>
          )}
        </>
      )}

      <ManagementModal
        open={serviceEditorMode !== null}
        eyebrow={
          serviceEditorMode === "create"
            ? "Create service"
            : serviceEditorMode === "edit"
              ? "Edit service"
              : "Service details"
        }
        title={serviceEditorMode === "create" ? "New service" : (selectedService?.name ?? "Service")}
        subtitle={selectedService ? `Code · ${selectedService.code}` : "Configure how the service is billed and paid."}
        icon={<BriefcaseBusiness />}
        busy={serviceSaving}
        onClose={() => {
          if (!serviceSaving) {
            setServiceEditorMode(null);
            setSelectedService(null);
          }
        }}
        footer={
          serviceEditorMode === "view" ? (
            <>
              <button type="button" className="management-secondary-action" onClick={() => setServiceEditorMode(null)}>
                Close
              </button>
              <button type="button" className="management-primary-action" onClick={() => setServiceEditorMode("edit")}>
                Edit service
              </button>
            </>
          ) : (
            <>
              <button type="button" className="management-secondary-action" onClick={() => setServiceEditorMode(null)}>
                Cancel
              </button>
              <button
                type="button"
                className="management-primary-action"
                disabled={serviceSaving}
                onClick={() => void saveService()}
              >
                {serviceSaving ? (
                  <>
                    <RefreshCw className="spin" /> Saving…
                  </>
                ) : serviceEditorMode === "create" ? (
                  "Create service"
                ) : (
                  "Save service"
                )}
              </button>
            </>
          )
        }
      >
        {serviceFormError && <div className="management-form-message">{serviceFormError}</div>}
        {serviceEditorMode === "view" && selectedService ? (
          <div className="services-pricing-detail-grid">
            <div>
              <span>Name</span>
              <strong>{selectedService.name}</strong>
            </div>
            <div>
              <span>Status</span>
              <strong>{statusLabel(selectedService.status)}</strong>
            </div>
            <div>
              <span>Client model</span>
              <strong>{pricingLabel(selectedService.client_pricing_model)}</strong>
            </div>
            <div>
              <span>Manager model</span>
              <strong>{pricingLabel(selectedService.manager_pricing_model)}</strong>
            </div>
            <div>
              <span>Sort order</span>
              <strong>{selectedService.sort_order}</strong>
            </div>
            <div>
              <span>Last updated</span>
              <strong>{formatDate(selectedService.updated_at)}</strong>
            </div>
            <div className="wide">
              <span>Description</span>
              <strong>{selectedService.description || "No description added yet."}</strong>
            </div>
            <div>
              <span>Client rates</span>
              <strong>{selectedService.active_client_rates}</strong>
            </div>
            <div>
              <span>Manager rates</span>
              <strong>{selectedService.active_manager_rates}</strong>
            </div>
          </div>
        ) : (
          <form className="management-form" onSubmit={(event) => event.preventDefault()}>
            <label className="management-field">
              <span>Service name</span>
              <div className="management-input">
                <input
                  value={serviceForm.name}
                  onChange={(event) => setServiceForm((current) => ({ ...current, name: event.target.value }))}
                  placeholder="Enter service name"
                />
              </div>
            </label>
            <label className="management-field">
              <span>Sort order</span>
              <div className="management-input">
                <input
                  type="number"
                  min="0"
                  value={serviceForm.sort_order}
                  onChange={(event) => setServiceForm((current) => ({ ...current, sort_order: event.target.value }))}
                  placeholder="0"
                />
              </div>
            </label>
            <label className="management-field wide">
              <span>Description</span>
              <div className="management-input textarea">
                <textarea
                  value={serviceForm.description}
                  onChange={(event) => setServiceForm((current) => ({ ...current, description: event.target.value }))}
                  placeholder="Describe the service delivery scope"
                />
              </div>
            </label>
            <label className="management-field">
              <span>Client billing model</span>
              <LooplessSelect
                value={serviceForm.client_pricing_model}
                options={pricingModelOptions}
                onValueChange={(value) =>
                  setServiceForm((current) => ({ ...current, client_pricing_model: value as PricingModeCode }))
                }
                ariaLabel="Client billing model"
              />
            </label>
            <label className="management-field">
              <span>Manager payout model</span>
              <LooplessSelect
                value={serviceForm.manager_pricing_model}
                options={pricingModelOptions}
                onValueChange={(value) =>
                  setServiceForm((current) => ({ ...current, manager_pricing_model: value as PricingModeCode }))
                }
                ariaLabel="Manager payout model"
              />
            </label>
            <label className="management-field">
              <span>Status</span>
              <LooplessSelect
                value={serviceForm.status}
                options={serviceStatusOptions.filter((option) => option.value) as { value: string; label: string }[]}
                onValueChange={(value) => setServiceForm((current) => ({ ...current, status: value as ServiceStatus }))}
                ariaLabel="Service status"
              />
            </label>
          </form>
        )}
      </ManagementModal>

      <ManagementModal
        open={pricingEditorMode !== null}
        eyebrow={pricingEditorMode === "edit" ? "Update pricing" : "Pricing history"}
        title={selectedPricingItem?.service_name ?? "Service pricing"}
        subtitle={activePricing ? `${activePricing.subject.name} · ${activePricing.subject.subtitle}` : ""}
        icon={activeTab === "clients" ? <Contact /> : <UserRound />}
        busy={pricingSaving}
        onClose={() => {
          if (!pricingSaving) {
            setPricingEditorMode(null);
            setSelectedPricingItem(null);
          }
        }}
        footer={
          pricingEditorMode === "view" ? (
            <>
              <button type="button" className="management-secondary-action" onClick={() => setPricingEditorMode(null)}>
                Close
              </button>
              {selectedPricingItem?.service_status === "ACTIVE" && (
                <button
                  type="button"
                  className="management-primary-action"
                  onClick={() => setPricingEditorMode("edit")}
                >
                  Edit pricing
                </button>
              )}
            </>
          ) : (
            <>
              <button type="button" className="management-secondary-action" onClick={() => setPricingEditorMode(null)}>
                Cancel
              </button>
              <button
                type="button"
                className="management-primary-action"
                disabled={pricingSaving}
                onClick={() => void savePricing()}
              >
                {pricingSaving ? (
                  <>
                    <RefreshCw className="spin" /> Saving…
                  </>
                ) : (
                  "Save pricing"
                )}
              </button>
            </>
          )
        }
      >
        {pricingFormError && <div className="management-form-message">{pricingFormError}</div>}
        {pricingEditorMode === "edit" && selectedPricingItem ? (
          <form className="management-form" onSubmit={(event) => event.preventDefault()}>
            <label className="management-field">
              <span>Pricing model</span>
              <LooplessSelect
                value={pricingForm.pricing_model}
                options={pricingModelOptions}
                onValueChange={(value) =>
                  setPricingForm((current) => ({ ...current, pricing_model: value as PricingModeCode }))
                }
                ariaLabel="Pricing model"
              />
            </label>
            <label className="management-field">
              <span>Amount</span>
              <div className="management-input">
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={pricingForm.amount}
                  onChange={(event) => setPricingForm((current) => ({ ...current, amount: event.target.value }))}
                  placeholder="0.00"
                />
              </div>
            </label>
            <label className="management-field">
              <span>Effective date</span>
              <div className="management-input">
                <input
                  type="date"
                  value={pricingForm.effective_date}
                  onChange={(event) =>
                    setPricingForm((current) => ({ ...current, effective_date: event.target.value }))
                  }
                />
              </div>
            </label>
            <label className="management-field">
              <span>Currency</span>
              <div className="management-input readonly">
                <input value={selectedPricingItem.current_rate?.currency ?? currency} readOnly />
              </div>
            </label>
            <label className="management-field wide">
              <span>Notes</span>
              <div className="management-input textarea">
                <textarea
                  value={pricingForm.notes}
                  onChange={(event) => setPricingForm((current) => ({ ...current, notes: event.target.value }))}
                  placeholder="Optional package or pricing notes"
                />
              </div>
            </label>
          </form>
        ) : (
          <div className="services-pricing-history">
            <div className="services-pricing-current-rate">
              <div>
                <span>Current rate</span>
                <strong>
                  {selectedPricingItem?.current_rate
                    ? formatMoney(selectedPricingItem.current_rate.amount, selectedPricingItem.current_rate.currency)
                    : "Not configured"}
                </strong>
              </div>
              <div>
                <span>Model</span>
                <strong>
                  {selectedPricingItem?.current_rate
                    ? pricingLabel(selectedPricingItem.current_rate.pricing_model)
                    : pricingLabel(selectedPricingItem?.default_pricing_model ?? "PER_VIDEO")}
                </strong>
              </div>
              <div>
                <span>Effective from</span>
                <strong>{formatDate(selectedPricingItem?.current_rate?.effective_from)}</strong>
              </div>
            </div>
            <div className="services-pricing-history-list">
              {(selectedPricingItem?.history ?? []).length === 0 ? (
                <div className="services-pricing-state empty compact">
                  <CircleDollarSign />
                  <strong>No pricing history</strong>
                  <span>This service has not been priced for the selected record yet.</span>
                </div>
              ) : (
                (selectedPricingItem?.history ?? []).map((entry) => (
                  <article key={entry.id}>
                    <div>
                      <strong>{formatMoney(entry.amount, entry.currency)}</strong>
                      <small>{pricingLabel(entry.pricing_model)}</small>
                    </div>
                    <div>
                      <span>{formatDate(entry.effective_from)}</span>
                      <small>{entry.created_by_name}</small>
                    </div>
                    <p>{entry.notes || "No notes provided."}</p>
                  </article>
                ))
              )}
            </div>
          </div>
        )}
      </ManagementModal>

      <ConfirmationDialog
        open={pendingServiceAction !== null}
        title={
          pendingServiceAction?.type === "delete"
            ? `Delete ${pendingServiceAction.service.name}?`
            : `${pendingServiceAction?.service.status === "ACTIVE" ? "Deactivate" : "Activate"} ${pendingServiceAction?.service.name}?`
        }
        description={
          pendingServiceAction?.type === "delete"
            ? "The service will be removed only when no pricing history exists for it."
            : pendingServiceAction?.service.status === "ACTIVE"
              ? "Inactive services stay in pricing history but stop appearing for new active configurations."
              : "Reactivated services become available again for future pricing changes."
        }
        confirmLabel={pendingServiceAction?.type === "delete" ? "Delete service" : "Confirm"}
        tone={pendingServiceAction?.type === "delete" ? "danger" : "primary"}
        loading={serviceSaving}
        onCancel={() => setPendingServiceAction(null)}
        onConfirm={() => void confirmServiceAction()}
      />
    </section>
  );
}
