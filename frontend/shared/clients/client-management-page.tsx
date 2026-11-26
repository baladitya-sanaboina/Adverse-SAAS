"use client";

import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  Activity,
  Building2,
  CircleDollarSign,
  ChevronLeft,
  ChevronRight,
  Globe2,
  Hash,
  MessageCircleMore,
  MessageSquareText,
  Mail,
  MapPin,
  NotebookTabs,
  Phone,
  Plus,
  RefreshCw,
  Search,
  Star,
  UserRound,
} from "lucide-react";
import { DashboardHero } from "@/components/dashboard/dashboard-hero";
import { ConfirmationDialog } from "@/components/foundation/confirmation-dialog";
import { CrudActionButtons } from "@/components/foundation/crud-action-buttons";
import { LooplessSelect } from "@/components/foundation/loopless-select";
import type { CurrentUser } from "@/lib/auth/types";
import "@loopless-shared/styles/client-management.css";

// Internal logins (Adverse IDs) use this domain (INTERNAL_EMAIL_DOMAIN on the server).
const INTERNAL_DOMAIN = "adverseindia.com";

type ClientStatus = "ACTIVE" | "INACTIVE";
type Client = {
  id: string;
  name: string;
  code: string;
  account_user_id: string | null;
  account_name: string | null;
  account_email: string | null;
  account_status: string | null;
  email: string | null;
  phone: string | null;
  website: string | null;
  address: string;
  city: string;
  state: string;
  country: string;
  status: ClientStatus;
  created_at: string;
  updated_at: string;
  primary_contact_name: string | null;
  primary_contact_email: string | null;
  primary_contact_phone: string | null;
  primary_contact_designation: string | null;
};
type Contact = {
  id: string;
  client_id: string;
  first_name: string;
  last_name: string;
  email: string | null;
  phone: string | null;
  designation: string;
  is_primary: boolean;
  status: ClientStatus;
  created_at: string;
  updated_at: string;
};
type ClientDetail = Client & { contacts: Contact[] };
type ClientHistoryItem = {
  id: string;
  client_id: string;
  created_by_id: string;
  created_by_name: string;
  content: string;
  created_at: string;
  updated_at: string;
};
type ClientActivityItem = {
  id: string;
  client_id: string;
  actor_id: string;
  actor_name: string;
  type: string;
  description: string;
  created_at: string;
};
type HistoryTab = "notes" | "feedback" | "activity";
type HistoryEditor = { type: "notes" | "feedback"; id: string | null } | null;
type ClientList = { items: Client[]; page: number; page_size: number; total: number; total_pages: number };
type Form = {
  name: string;
  code: string;
  email: string;
  portal_login_email: string;
  phone: string;
  website: string;
  address: string;
  city: string;
  state: string;
  country: string;
  status: ClientStatus;
};
type Mode = "list" | "create" | "view" | "edit";
type ContactForm = {
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  designation: string;
  is_primary: boolean;
  status: ClientStatus;
};
type PricingModeCode = "PER_VIDEO" | "PER_PIECE" | "MONTHLY_FIXED" | "MONTHLY_PACKAGE" | "COMMISSION_PER_DELIVERABLE";
type PricingRecord = {
  id: string;
  scope: "CLIENT" | "MANAGER";
  pricing_model: PricingModeCode;
  amount: string | number;
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
  service_status: ClientStatus;
  default_pricing_model: PricingModeCode;
  configured: boolean;
  current_rate: PricingRecord | null;
  history_count: number;
  history: PricingRecord[];
};
type PricingOverview = {
  scope: "CLIENT";
  subject: { id: string; name: string; subtitle: string };
  items: PricingItem[];
  total_services: number;
  configured_services: number;
  missing_services: number;
};
type PricingForm = {
  pricing_model: PricingModeCode;
  amount: string;
  effective_date: string;
  notes: string;
};
type PricingEditorMode = "view" | "edit" | null;

const empty: Form = {
  name: "",
  code: "",
  email: "",
  portal_login_email: "",
  phone: "",
  website: "",
  address: "",
  city: "",
  state: "",
  country: "",
  status: "ACTIVE",
};
const emptyContact: ContactForm = {
  first_name: "",
  last_name: "",
  email: "",
  phone: "",
  designation: "",
  is_primary: false,
  status: "ACTIVE",
};
const emptyPricingForm: PricingForm = {
  pricing_model: "PER_VIDEO",
  amount: "",
  effective_date: "",
  notes: "",
};
const pricingModelOptions = [
  { value: "PER_VIDEO", label: "Per video" },
  { value: "PER_PIECE", label: "Per piece" },
  { value: "MONTHLY_FIXED", label: "Monthly fixed" },
  { value: "MONTHLY_PACKAGE", label: "Monthly package" },
  { value: "COMMISSION_PER_DELIVERABLE", label: "Commission / per deliverable" },
] as const;
const messageFrom = (value: unknown, fallback: string) => {
  if (value && typeof value === "object" && "detail" in value) {
    const detail = (value as { detail?: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail[0] && typeof detail[0] === "object" && "msg" in detail[0]) {
      return String((detail[0] as { msg: unknown }).msg).replace(/^Value error, /, "");
    }
  }
  return fallback;
};

const pricingLabel = (value: PricingModeCode) =>
  pricingModelOptions.find((option) => option.value === value)?.label ?? value;

const money = (amount: string | number, currency: string) => {
  const numeric = typeof amount === "number" ? amount : Number(amount);
  if (!Number.isFinite(numeric)) return `0 ${currency}`;
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(numeric);
};

const toDateTimeLocal = (value?: string | null) => {
  const source = value ? new Date(value) : new Date();
  const offset = source.getTimezoneOffset();
  const local = new Date(source.getTime() - offset * 60_000);
  return local.toISOString().slice(0, 16);
};

const validationErrorsFrom = (value: unknown) => {
  if (!value || typeof value !== "object" || !("errors" in value)) return {};
  const errors = (value as { errors?: unknown }).errors;
  if (!Array.isArray(errors)) return {};
  return errors.reduce<Record<string, string>>((result, error) => {
    if (!error || typeof error !== "object") return result;
    const location = "loc" in error && Array.isArray(error.loc) ? error.loc : [];
    const field = location.at(-1);
    if (typeof field !== "string" || !(field in empty)) return result;
    const message = "msg" in error ? String(error.msg).replace(/^Value error, /, "") : "Check this value.";
    result[field] = message;
    return result;
  }, {});
};

export function ClientManagementPage({
  initialClientId,
  renderWork,
}: {
  initialClientId?: string;
  /** Admin app only: the client's videos and money, shown under the client info. */
  renderWork?: (clientId: string) => ReactNode;
}) {
  const router = useRouter();
  const [result, setResult] = useState<ClientList | null>(null);
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [mode, setMode] = useState<Mode>(initialClientId ? "view" : "list");
  const [selected, setSelected] = useState<ClientDetail | null>(null);
  const [form, setForm] = useState<Form>(empty);
  const [contactForm, setContactForm] = useState<ContactForm>(emptyContact);
  const [editingContact, setEditingContact] = useState<Contact | null>(null);
  const [contactEditorOpen, setContactEditorOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(Boolean(initialClientId));
  const [saving, setSaving] = useState(false);
  const [openingId, setOpeningId] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [contactErrors, setContactErrors] = useState<Record<string, string>>({});
  const [touched, setTouched] = useState<Record<string, boolean>>({});
  const [contactTouched, setContactTouched] = useState<Record<string, boolean>>({});
  const pageNumbers = useMemo(() => {
    const totalPages = Math.max(result?.total_pages ?? 0, 1);
    const visiblePages = Math.min(totalPages, 5);
    const start = Math.max(1, Math.min(page - 2, totalPages - visiblePages + 1));
    return Array.from({ length: visiblePages }, (_, index) => start + index);
  }, [page, result?.total_pages]);
  const [pendingStatus, setPendingStatus] = useState<Client | null>(null);
  const [historyTab, setHistoryTab] = useState<HistoryTab>("notes");
  const [notes, setNotes] = useState<ClientHistoryItem[]>([]);
  const [feedback, setFeedback] = useState<ClientHistoryItem[]>([]);
  const [activities, setActivities] = useState<ClientActivityItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState<Record<HistoryTab, boolean>>({
    notes: false,
    feedback: false,
    activity: false,
  });
  const [historyErrors, setHistoryErrors] = useState<Record<HistoryTab, string>>({
    notes: "",
    feedback: "",
    activity: "",
  });
  const [historyEditor, setHistoryEditor] = useState<HistoryEditor>(null);
  const [historyContent, setHistoryContent] = useState("");
  const [historyContentTouched, setHistoryContentTouched] = useState(false);
  const [historySaving, setHistorySaving] = useState(false);
  const [pendingNoteDelete, setPendingNoteDelete] = useState<ClientHistoryItem | null>(null);
  const [clientPricing, setClientPricing] = useState<PricingOverview | null>(null);
  const [pricingLoading, setPricingLoading] = useState(false);
  const [pricingError, setPricingError] = useState("");
  const [selectedPricingItem, setSelectedPricingItem] = useState<PricingItem | null>(null);
  const [pricingEditorMode, setPricingEditorMode] = useState<PricingEditorMode>(null);
  const [pricingForm, setPricingForm] = useState<PricingForm>(emptyPricingForm);
  const [pricingFormError, setPricingFormError] = useState("");
  const [pricingSaving, setPricingSaving] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<Client | null>(null);

  const query = useMemo(() => {
    const params = new URLSearchParams({ page: String(page), page_size: "20" });
    if (search) params.set("search", search);
    if (status) params.set("status", status);
    return params.toString();
  }, [page, search, status]);
  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [clientsResponse, meResponse] = await Promise.all([
        fetch(`/api/company/clients?${query}`, { cache: "no-store" }),
        fetch("/api/auth/me", { cache: "no-store" }),
      ]);
      const [clientsData, meData] = await Promise.all([clientsResponse.json(), meResponse.json()]);
      if (!clientsResponse.ok) throw new Error(messageFrom(clientsData, "Unable to load clients."));
      setResult(clientsData);
      if (meResponse.ok) setCurrentUser(meData);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to load clients.");
    } finally {
      setLoading(false);
    }
  }, [query]);
  const loadHistorySection = useCallback(async (id: string, section: HistoryTab) => {
    setHistoryLoading((current) => ({ ...current, [section]: true }));
    setHistoryErrors((current) => ({ ...current, [section]: "" }));
    try {
      const response = await fetch(`/api/company/clients/${id}/${section}`, { cache: "no-store" });
      const data = await response.json();
      if (!response.ok) throw new Error(messageFrom(data, `Unable to load client ${section}.`));
      if (section === "notes") setNotes(data.items ?? []);
      if (section === "feedback") setFeedback(data.items ?? []);
      if (section === "activity") setActivities(data.items ?? []);
    } catch (reason) {
      setHistoryErrors((current) => ({
        ...current,
        [section]: reason instanceof Error ? reason.message : `Unable to load client ${section}.`,
      }));
    } finally {
      setHistoryLoading((current) => ({ ...current, [section]: false }));
    }
  }, []);
  const loadHistory = useCallback(
    async (id: string) => {
      await Promise.all([
        loadHistorySection(id, "notes"),
        loadHistorySection(id, "feedback"),
        loadHistorySection(id, "activity"),
      ]);
    },
    [loadHistorySection],
  );
  const loadClientPricing = useCallback(async (clientId: string) => {
    setPricingLoading(true);
    setPricingError("");
    try {
      const response = await fetch(`/api/company/pricing/clients/${clientId}?include_history=true`, {
        cache: "no-store",
      });
      const data = (await response.json()) as PricingOverview | { detail?: string };
      if (!response.ok) throw new Error(messageFrom(data, "Unable to load client pricing."));
      setClientPricing(data as PricingOverview);
      setSelectedPricingItem((current) => {
        const items = (data as PricingOverview).items;
        return current ? (items.find((item) => item.service_id === current.service_id) ?? null) : null;
      });
    } catch (reason) {
      setPricingError(reason instanceof Error ? reason.message : "Unable to load client pricing.");
    } finally {
      setPricingLoading(false);
    }
  }, []);
  const loadDetail = useCallback(
    async (id: string) => {
      setDetailLoading(true);
      setError("");
      setClientPricing(null);
      setSelectedPricingItem(null);
      setPricingEditorMode(null);
      setPricingError("");
      try {
        const [clientResponse, meResponse] = await Promise.all([
          fetch(`/api/company/clients/${id}`, { cache: "no-store" }),
          fetch("/api/auth/me", { cache: "no-store" }),
        ]);
        const [clientData, meData] = await Promise.all([clientResponse.json(), meResponse.json()]);
        if (!clientResponse.ok) throw new Error(messageFrom(clientData, "Unable to load client details."));
        setSelected(clientData);
        setForm({
          name: clientData.name,
          code: clientData.code,
          email: clientData.email ?? "",
          portal_login_email: clientData.account_email ?? "",
          phone: clientData.phone ?? "",
          website: clientData.website ?? "",
          address: clientData.address,
          city: clientData.city,
          state: clientData.state,
          country: clientData.country,
          status: clientData.status,
        });
        if (meResponse.ok) setCurrentUser(meData);
        if (meResponse.ok && meData.role?.code !== "COMPANY_CLIENT") void loadHistory(id);
        if (meResponse.ok && meData.role?.code === "COMPANY_ADMIN") void loadClientPricing(id);
      } catch (reason) {
        setSelected(null);
        setError(reason instanceof Error ? reason.message : "Unable to load client details.");
      } finally {
        setDetailLoading(false);
        setLoading(false);
      }
    },
    [loadClientPricing, loadHistory],
  );
  useEffect(() => {
    const timer = window.setTimeout(() => {
      if (initialClientId) {
        void loadDetail(initialClientId);
        return;
      }
      if (new URLSearchParams(window.location.search).get("mode") === "create") {
        setMode("create");
        setLoading(false);
        void fetch("/api/auth/me", { cache: "no-store" })
          .then(async (response) => ({ response, data: await response.json() }))
          .then(({ response, data }) => {
            if (response.ok) setCurrentUser(data);
          });
        return;
      }
      void load();
    }, 220);
    return () => window.clearTimeout(timer);
  }, [initialClientId, load, loadDetail]);

  const hasPermission = (action: string) =>
    Boolean(
      currentUser?.permissions.some((permission) => permission.module === "CLIENTS" && permission.action === action),
    );
  const hasSettingsPermission = (action: string) =>
    Boolean(
      currentUser?.permissions.some((permission) => permission.module === "SETTINGS" && permission.action === action),
    );
  const canCreate = hasPermission("CREATE");
  const canEdit = hasPermission("EDIT");
  const canManage = hasPermission("MANAGE");
  const canDelete = hasPermission("DELETE");
  const canViewHistory = hasPermission("VIEW") && currentUser?.role.code !== "COMPANY_CLIENT";
  const canViewPricing = currentUser?.role.code === "COMPANY_ADMIN" && hasSettingsPermission("VIEW");
  const canManagePricing = currentUser?.role.code === "COMPANY_ADMIN" && hasSettingsPermission("MANAGE");

  function openCreate() {
    setMode("create");
    setForm(empty);
    setSelected(null);
    setClientPricing(null);
    setSelectedPricingItem(null);
    setPricingEditorMode(null);
    setFieldErrors({});
    setTouched({});
    setError("");
  }
  async function openClient(client: Client, nextMode: "view" | "edit") {
    if (nextMode === "view") {
      router.push(`/clients/${client.id}`);
      return;
    }
    setOpeningId(client.id);
    setError("");
    try {
      const response = await fetch(`/api/company/clients/${client.id}`, { cache: "no-store" });
      const data = await response.json();
      if (!response.ok) throw new Error(messageFrom(data, "Unable to open client."));
      setSelected(data);
      setForm({
        name: data.name,
        code: data.code,
        email: data.email ?? "",
        portal_login_email: data.account_email ?? "",
        phone: data.phone ?? "",
        website: data.website ?? "",
        address: data.address,
        city: data.city,
        state: data.state,
        country: data.country,
        status: data.status,
      });
      setMode(nextMode);
      setFieldErrors({});
      setTouched({});
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to open client.");
    } finally {
      setOpeningId("");
    }
  }
  function update(key: keyof Form, value: string) {
    setForm((current) => ({ ...current, [key]: value }));
    if (touched[key]) setFieldErrors((current) => ({ ...current, [key]: validateField(key, value) }));
  }
  function touchField(key: keyof Form) {
    setTouched((current) => ({ ...current, [key]: true }));
    setFieldErrors((current) => ({ ...current, [key]: validateField(key, form[key]) }));
  }
  function validateField(key: keyof Form, value: string) {
    if (key === "name" && value.trim().length < 2) return "Enter at least 2 characters.";
    if (key === "name" && value.trim().length > 160) return "Use no more than 160 characters.";
    // New clients get their code automatically (CLT-0001, ...; owner request 2026-11-19).
    if (key === "code" && mode === "create") return "";
    if (key === "code" && !/^[A-Za-z0-9-]{2,30}$/.test(value.trim())) return "Use 2–30 letters, numbers or hyphens.";
    if (key === "email" && mode === "create" && !value.trim()) return "Business email is required.";
    if (key === "email" && value && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) return "Enter a valid email address.";
    // Optional for clients (owner request 2026-11-19): they sign in with their Gmail (the
    // email above); an Adverse ID for their mailbox is made from the name when left empty.
    if (key === "portal_login_email" && value && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value))
      return "Enter a valid email address.";
    // Owner rule 2026-11-26: the Adverse ID is always @adverseindia.com; their own email is not.
    if (key === "portal_login_email" && value && !value.trim().toLowerCase().endsWith(`@${INTERNAL_DOMAIN}`))
      return `The Adverse ID must end with @${INTERNAL_DOMAIN}.`;
    if (key === "email" && mode === "create" && value.trim().toLowerCase().endsWith(`@${INTERNAL_DOMAIN}`))
      return `Use the client's own email (Gmail), not an @${INTERNAL_DOMAIN} address.`;
    if (key === "phone" && mode === "create" && !value.trim()) return "Mobile number is required.";
    if (key === "phone" && value && !/^\+?[0-9 ()-]{7,24}$/.test(value.trim())) {
      return "Enter a valid phone number using 7–24 characters.";
    }
    if (key === "website" && value && !/^https?:\/\/.+/.test(value)) return "Include http:// or https://.";
    if (key === "address" && value.trim().length > 300) return "Use no more than 300 characters.";
    if (["city", "state", "country"].includes(key) && value.trim().length > 100) {
      return "Use no more than 100 characters.";
    }
    return "";
  }
  async function save(event: React.FormEvent) {
    event.preventDefault();
    const errors = Object.fromEntries(
      (Object.keys(form) as Array<keyof Form>).map((key) => [key, validateField(key, form[key])]),
    );
    setFieldErrors(errors);
    setTouched(Object.fromEntries(Object.keys(form).map((key) => [key, true])));
    if (Object.values(errors).some(Boolean)) return;
    setSaving(true);
    setError("");
    const editing = mode === "edit" && selected;
    try {
      const response = await fetch(editing ? `/api/company/clients/${selected.id}` : "/api/company/clients", {
        method: editing ? "PATCH" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: form.name.trim(),
          ...(editing ? { code: form.code.trim() } : {}),
          email: form.email.trim() || null,
          ...(!editing && form.portal_login_email.trim() ? { portal_login_email: form.portal_login_email.trim() } : {}),
          phone: form.phone.trim() || null,
          website: form.website.trim() || null,
          address: form.address.trim(),
          city: form.city.trim(),
          state: form.state.trim(),
          country: form.country.trim(),
          ...(editing ? { status: form.status } : {}),
        }),
      });
      const data = await response.json();
      if (!response.ok) {
        const serverErrors = validationErrorsFrom(data);
        if (Object.keys(serverErrors).length) {
          setFieldErrors((current) => ({ ...current, ...serverErrors }));
          setTouched((current) => ({
            ...current,
            ...Object.fromEntries(Object.keys(serverErrors).map((key) => [key, true])),
          }));
          return;
        }
        if (data && typeof data === "object" && "code" in data && data.code === "CLIENT_CODE_EXISTS") {
          setFieldErrors((current) => ({ ...current, code: "This client code is already in use." }));
          setTouched((current) => ({ ...current, code: true }));
          return;
        }
        // The login checks run before the client is saved (owner rule 2026-11-26).
        const loginField =
          data && typeof data === "object" && "code" in data
            ? (
                {
                  LOGIN_NOT_INTERNAL: "portal_login_email",
                  LOGIN_TAKEN: "portal_login_email",
                  GMAIL_IS_INTERNAL: "email",
                  GMAIL_IN_USE: "email",
                  GMAIL_REQUIRED: "email",
                  GMAIL_SAME_AS_LOGIN: "portal_login_email",
                } as Record<string, keyof Form>
              )[String(data.code)]
            : undefined;
        if (loginField) {
          setFieldErrors((current) => ({ ...current, [loginField]: messageFrom(data, "Check this address.") }));
          setTouched((current) => ({ ...current, [loginField]: true }));
          return;
        }
        if (data && typeof data === "object" && "code" in data && data.code === "CLIENT_EMAIL_EXISTS") {
          setFieldErrors((current) => ({ ...current, email: "This client email is already in use." }));
          setTouched((current) => ({ ...current, email: true }));
          return;
        }
        throw new Error(messageFrom(data, "Unable to save client."));
      }
      let nextNotice = editing
        ? "Client updated successfully."
        : `Client created successfully. Client code: ${typeof data.code === "string" ? data.code : "set automatically"}.`;
      if (!editing && form.email.trim()) {
        try {
          const inviteResponse = await fetch("/api/company/invitations", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              name: form.name.trim(),
              ...(form.portal_login_email.trim() ? { email: form.portal_login_email.trim() } : {}),
              notification_email: form.email.trim(),
              phone_number: form.phone.trim(),
              role_code: "COMPANY_CLIENT",
              client_id: data.id,
            }),
          });
          const inviteData = await inviteResponse.json();
          if (!inviteResponse.ok) {
            throw new Error(messageFrom(inviteData, "Unable to send the client activation email."));
          }
          const adverseId = typeof inviteData.email === "string" ? inviteData.email : form.portal_login_email.trim();
          nextNotice = `Client created successfully (code ${typeof data.code === "string" ? data.code : "set automatically"}). Activation email sent to ${form.email.trim()}; they sign in with that Gmail${adverseId ? ` or their Adverse ID ${adverseId}` : ""}.`;
        } catch (inviteReason) {
          nextNotice =
            inviteReason instanceof Error
              ? `Client created, but activation email was not sent: ${inviteReason.message}`
              : "Client created, but activation email was not sent.";
        }
      }
      setNotice(nextNotice);
      if (initialClientId && editing) {
        await loadDetail(initialClientId);
        setMode("view");
      } else {
        setMode("list");
        setSelected(null);
        await load();
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to save client.");
    } finally {
      setSaving(false);
    }
  }
  async function changeStatus() {
    if (!pendingStatus) return;
    setSaving(true);
    const next = pendingStatus.status === "ACTIVE" ? "INACTIVE" : "ACTIVE";
    try {
      const response = await fetch(`/api/company/clients/${pendingStatus.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: next }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(messageFrom(data, "Unable to update client status."));
      setNotice(`Client ${next === "ACTIVE" ? "enabled" : "disabled"} successfully.`);
      setPendingStatus(null);
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to update client status.");
      setPendingStatus(null);
    } finally {
      setSaving(false);
    }
  }

  async function deleteClient() {
    if (!pendingDelete) return;
    setSaving(true);
    setError("");
    try {
      const response = await fetch(`/api/company/clients/${pendingDelete.id}`, { method: "DELETE" });
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(messageFrom(data, "Unable to delete client."));
      }
      setNotice(`${pendingDelete.name} deleted successfully.`);
      setPendingDelete(null);
      if (initialClientId) {
        router.push("/clients");
        return;
      }
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to delete client.");
      setPendingDelete(null);
    } finally {
      setSaving(false);
    }
  }

  function backToClients() {
    if (initialClientId) {
      router.push("/clients");
      return;
    }
    setMode("list");
    setSelected(null);
    setClientPricing(null);
    setSelectedPricingItem(null);
    setPricingEditorMode(null);
    setContactEditorOpen(false);
    setError("");
    void load();
  }

  function openPricing(item: PricingItem, mode: PricingEditorMode) {
    setSelectedPricingItem(item);
    setPricingEditorMode(mode);
    setPricingForm({
      pricing_model: item.current_rate?.pricing_model ?? item.default_pricing_model,
      amount: item.current_rate ? String(item.current_rate.amount) : "",
      effective_date: toDateTimeLocal(item.current_rate?.effective_from),
      notes: item.current_rate?.notes ?? "",
    });
    setPricingFormError("");
  }

  async function savePricing() {
    if (!selected || !selectedPricingItem) return;
    if (!pricingForm.amount || Number(pricingForm.amount) < 0) {
      setPricingFormError("Enter a valid pricing amount.");
      return;
    }
    setPricingSaving(true);
    setPricingFormError("");
    try {
      const response = await fetch(
        `/api/company/pricing/clients/${selected.id}/services/${selectedPricingItem.service_id}`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            pricing_model: pricingForm.pricing_model,
            amount: pricingForm.amount,
            effective_from: new Date(pricingForm.effective_date || toDateTimeLocal()).toISOString(),
            notes: pricingForm.notes.trim() || null,
          }),
        },
      );
      const data = await response.json();
      if (!response.ok) throw new Error(messageFrom(data, "Unable to save pricing."));
      setNotice(`Client pricing updated for ${selectedPricingItem.service_name}.`);
      await loadClientPricing(selected.id);
      setPricingEditorMode("view");
    } catch (reason) {
      setPricingFormError(reason instanceof Error ? reason.message : "Unable to save pricing.");
    } finally {
      setPricingSaving(false);
    }
  }

  function validateContactField(key: keyof ContactForm, value: string | boolean) {
    if (key === "first_name" && String(value).trim().length < 1) return "First name is required.";
    if (key === "email" && value && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(value))) {
      return "Enter a valid email address.";
    }
    if (key === "phone" && value && !/^\+?[0-9 ()-]{7,24}$/.test(String(value))) {
      return "Enter a valid phone number.";
    }
    return "";
  }

  function updateContact(key: keyof ContactForm, value: string | boolean) {
    setContactForm((current) => ({ ...current, [key]: value }));
    if (contactTouched[key]) {
      setContactErrors((current) => ({ ...current, [key]: validateContactField(key, value) }));
    }
  }

  function touchContact(key: keyof ContactForm) {
    setContactTouched((current) => ({ ...current, [key]: true }));
    setContactErrors((current) => ({ ...current, [key]: validateContactField(key, contactForm[key]) }));
  }

  function openContactEditor(contact?: Contact) {
    setEditingContact(contact ?? null);
    setContactForm(
      contact
        ? {
            first_name: contact.first_name,
            last_name: contact.last_name,
            email: contact.email ?? "",
            phone: contact.phone ?? "",
            designation: contact.designation,
            is_primary: contact.is_primary,
            status: contact.status,
          }
        : emptyContact,
    );
    setContactErrors({});
    setContactTouched({});
    setError("");
    setContactEditorOpen(true);
  }

  async function saveContact(event: React.FormEvent) {
    event.preventDefault();
    if (!selected) return;
    const errors = Object.fromEntries(
      (Object.keys(contactForm) as Array<keyof ContactForm>).map((key) => [
        key,
        validateContactField(key, contactForm[key]),
      ]),
    );
    setContactErrors(errors);
    setContactTouched(Object.fromEntries(Object.keys(contactForm).map((key) => [key, true])));
    if (Object.values(errors).some(Boolean)) return;
    setSaving(true);
    setError("");
    try {
      const path = editingContact
        ? `/api/company/clients/${selected.id}/contacts/${editingContact.id}`
        : `/api/company/clients/${selected.id}/contacts`;
      const response = await fetch(path, {
        method: editingContact ? "PATCH" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          first_name: contactForm.first_name.trim(),
          last_name: contactForm.last_name.trim(),
          email: contactForm.email.trim() || null,
          phone: contactForm.phone.trim() || null,
          designation: contactForm.designation.trim(),
          is_primary: contactForm.is_primary,
          status: contactForm.status,
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(messageFrom(data, "Unable to save contact."));
      setNotice(`Contact ${editingContact ? "updated" : "added"} successfully.`);
      setContactEditorOpen(false);
      setEditingContact(null);
      await loadDetail(selected.id);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to save contact.");
    } finally {
      setSaving(false);
    }
  }

  function historyValidation(value: string) {
    const normalized = value.trim();
    if (!normalized) return "Enter a note before saving.";
    if (normalized.length > 4000) return "Use no more than 4000 characters.";
    return "";
  }

  function openHistoryEditor(type: "notes" | "feedback", item?: ClientHistoryItem) {
    setHistoryTab(type);
    setHistoryEditor({ type, id: item?.id ?? null });
    setHistoryContent(item?.content ?? "");
    setHistoryContentTouched(false);
    setHistoryErrors((current) => ({ ...current, [type]: "" }));
  }

  function closeHistoryEditor() {
    setHistoryEditor(null);
    setHistoryContent("");
    setHistoryContentTouched(false);
  }

  async function saveHistory(event: React.FormEvent) {
    event.preventDefault();
    if (!selected || !historyEditor) return;
    setHistoryContentTouched(true);
    if (historyValidation(historyContent)) return;
    setHistorySaving(true);
    const { type, id } = historyEditor;
    const path = id
      ? `/api/company/clients/${selected.id}/${type}/${id}`
      : `/api/company/clients/${selected.id}/${type}`;
    try {
      const response = await fetch(path, {
        method: id ? "PATCH" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: historyContent.trim() }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(messageFrom(data, `Unable to save client ${type}.`));
      setNotice(`${type === "notes" ? "Note" : "Feedback"} ${id ? "updated" : "added"} successfully.`);
      closeHistoryEditor();
      await Promise.all([loadHistorySection(selected.id, type), loadHistorySection(selected.id, "activity")]);
    } catch (reason) {
      setHistoryErrors((current) => ({
        ...current,
        [type]: reason instanceof Error ? reason.message : `Unable to save client ${type}.`,
      }));
    } finally {
      setHistorySaving(false);
    }
  }

  async function deleteNote() {
    if (!selected || !pendingNoteDelete) return;
    setHistorySaving(true);
    try {
      const response = await fetch(`/api/company/clients/${selected.id}/notes/${pendingNoteDelete.id}`, {
        method: "DELETE",
      });
      if (!response.ok) {
        const data = await response.json();
        throw new Error(messageFrom(data, "Unable to delete this client note."));
      }
      setPendingNoteDelete(null);
      setNotice("Note deleted successfully.");
      await Promise.all([loadHistorySection(selected.id, "notes"), loadHistorySection(selected.id, "activity")]);
    } catch (reason) {
      setPendingNoteDelete(null);
      setHistoryErrors((current) => ({
        ...current,
        notes: reason instanceof Error ? reason.message : "Unable to delete this client note.",
      }));
    } finally {
      setHistorySaving(false);
    }
  }

  function relativeTime(value: string) {
    const difference = Date.now() - new Date(value).getTime();
    const minutes = Math.max(0, Math.floor(difference / 60000));
    if (minutes < 1) return "Just now";
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    if (days < 7) return `${days}d ago`;
    return new Date(value).toLocaleDateString();
  }

  const fields: Array<{ key: keyof Form; label: string; icon: typeof Building2; wide?: boolean }> = [
    { key: "name", label: "Client name", icon: Building2 },
    ...(mode === "edit" ? ([{ key: "code", label: "Client code", icon: Hash }] as const) : []),
    { key: "email", label: "Business email", icon: Mail },
    ...(mode === "create"
      ? ([
          {
            key: "portal_login_email",
            label: "Adverse ID (name@adverseindia.com, optional: made from the name)",
            icon: Mail,
          },
        ] as const)
      : []),
    { key: "phone", label: "Mobile number", icon: Phone },
    { key: "website", label: "Website", icon: Globe2 },
    { key: "address", label: "Address", icon: MapPin, wide: true },
    { key: "city", label: "City", icon: MapPin },
    { key: "state", label: "State", icon: MapPin },
    { key: "country", label: "Country", icon: MapPin },
  ];
  const contactFields: Array<{ key: keyof ContactForm; label: string; icon: typeof UserRound }> = [
    { key: "first_name", label: "First name", icon: UserRound },
    { key: "last_name", label: "Last name", icon: UserRound },
    { key: "email", label: "Email", icon: Mail },
    { key: "phone", label: "Phone", icon: Phone },
    { key: "designation", label: "Designation", icon: Building2 },
  ];
  const actionsFor = (client: Client) => (
    <CrudActionButtons
      view={{
        label: `Open ${client.name} workspace, notes and activity`,
        onClick: () => void openClient(client, "view"),
        disabled: Boolean(openingId),
        loading: openingId === client.id,
        icon: NotebookTabs,
      }}
      edit={
        canEdit
          ? {
              label: `Edit ${client.name}`,
              onClick: () => void openClient(client, "edit"),
              disabled: Boolean(openingId),
            }
          : undefined
      }
      toggle={
        canEdit
          ? {
              label: `${client.status === "ACTIVE" ? "Disable" : "Enable"} ${client.name}`,
              onClick: () => setPendingStatus(client),
            }
          : undefined
      }
      remove={
        canDelete && (!client.account_status || client.account_status === "PENDING_VERIFICATION")
          ? {
              label: `Delete ${client.name}`,
              onClick: () => setPendingDelete(client),
            }
          : undefined
      }
      active={client.status === "ACTIVE"}
    />
  );
  return (
    <>
      <DashboardHero
        title=""
        highlight="Clients"
        description="Manage tenant-scoped client businesses and contacts."
        compact
      />
      <div className="dash-content">
        <section className="client-management" aria-live="polite">
          {notice && (
            <div className="client-notice" role="status">
              {notice}
            </div>
          )}
          {mode === "list" ? (
            <>
              <header className="management-toolbar">
                <div>
                  <span>Client directory</span>
                  <strong>{result?.total ?? 0} Clients</strong>
                </div>
                {canCreate && (
                  <button type="button" onClick={openCreate}>
                    <Plus /> Create client
                  </button>
                )}
              </header>
              <div className="client-filters">
                <label>
                  <Search />
                  <input
                    value={search}
                    onChange={(event) => {
                      setSearch(event.target.value);
                      setPage(1);
                    }}
                    placeholder="Search name, code or email"
                    aria-label="Search clients"
                  />
                </label>
                <LooplessSelect
                  value={status}
                  onValueChange={(value) => {
                    setStatus(value);
                    setPage(1);
                  }}
                  ariaLabel="Filter clients by status"
                  options={[
                    { value: "", label: "All statuses" },
                    { value: "ACTIVE", label: "Active" },
                    { value: "INACTIVE", label: "Inactive" },
                  ]}
                />
              </div>
              {error ? (
                <div className="client-state error">
                  <strong>{error}</strong>
                  <button onClick={() => void load()}>Retry</button>
                </div>
              ) : loading ? (
                <div className="client-state">
                  <i /> Loading clients…
                </div>
              ) : result?.items.length ? (
                <>
                  <div className="client-table" role="table" aria-label="Client directory">
                    <header role="row">
                      <span>Client</span>
                      <span>Contact</span>
                      <span>Location</span>
                      <span>Status</span>
                      <span>Created</span>
                      <span>Actions</span>
                    </header>
                    {result.items.map((client) => (
                      <article key={client.id} role="row">
                        <div>
                          <b>{client.name.slice(0, 2).toUpperCase()}</b>
                          <span>
                            <strong>{client.name}</strong>
                            <small>{client.code}</small>
                          </span>
                        </div>
                        <span>
                          <strong>{client.primary_contact_name || "No primary contact"}</strong>
                          <small>{client.primary_contact_email || client.primary_contact_phone || "—"}</small>
                        </span>
                        <span>{[client.city, client.country].filter(Boolean).join(", ") || "—"}</span>
                        <em className={client.status.toLowerCase()}>{client.status}</em>
                        <span>{new Date(client.created_at).toLocaleDateString()}</span>
                        {actionsFor(client)}
                      </article>
                    ))}
                  </div>
                  <div className="client-mobile-list" aria-label="Client directory mobile cards">
                    {result.items.map((client) => (
                      <article key={client.id}>
                        <header>
                          <b>{client.name.slice(0, 2).toUpperCase()}</b>
                          <div>
                            <strong>{client.name}</strong>
                            <span>{client.code}</span>
                          </div>
                          <em className={client.status.toLowerCase()}>{client.status}</em>
                        </header>
                        <dl>
                          <div>
                            <dt>Primary contact</dt>
                            <dd>{client.primary_contact_name || "Not assigned"}</dd>
                          </div>
                          <div>
                            <dt>Contact</dt>
                            <dd>{client.primary_contact_email || client.primary_contact_phone || "—"}</dd>
                          </div>
                          <div>
                            <dt>Location</dt>
                            <dd>{[client.city, client.country].filter(Boolean).join(", ") || "—"}</dd>
                          </div>
                        </dl>
                        {actionsFor(client)}
                      </article>
                    ))}
                  </div>
                </>
              ) : (
                <div className="client-state">
                  <Building2 />
                  <strong>No clients found</strong>
                </div>
              )}
              <footer className="client-pagination">
                <span>
                  Page {result?.page ?? 1} of {Math.max(result?.total_pages ?? 0, 1)} · {result?.total ?? 0} results
                </span>
                <div>
                  <button
                    type="button"
                    aria-label="Previous page"
                    disabled={page <= 1}
                    onClick={() => setPage(page - 1)}
                  >
                    <ChevronLeft />
                  </button>
                  {pageNumbers.map((pageNumber) => (
                    <button
                      key={pageNumber}
                      type="button"
                      className={pageNumber === page ? "active" : undefined}
                      aria-label={`Go to page ${pageNumber}`}
                      aria-current={pageNumber === page ? "page" : undefined}
                      onClick={() => setPage(pageNumber)}
                    >
                      {pageNumber}
                    </button>
                  ))}
                  <button
                    type="button"
                    aria-label="Next page"
                    disabled={!result || page >= result.total_pages}
                    onClick={() => setPage(page + 1)}
                  >
                    <ChevronRight />
                  </button>
                </div>
              </footer>
            </>
          ) : (
            <>
              <header className="management-toolbar">
                <button type="button" className="management-back" onClick={backToClients}>
                  <ArrowLeft /> Back to clients
                </button>
                <span>{mode === "create" ? "New Client" : mode === "edit" ? "Edit Client" : "Client Details"}</span>
              </header>
              {detailLoading ? (
                <div className="client-state">
                  <i /> Loading client details…
                </div>
              ) : error && mode === "view" && !selected ? (
                <div className="client-state error" role="alert">
                  <strong>{error}</strong>
                  <div className="client-state-actions">
                    <button type="button" onClick={backToClients}>
                      Back to clients
                    </button>
                    {initialClientId && (
                      <button type="button" onClick={() => void loadDetail(initialClientId)}>
                        Retry
                      </button>
                    )}
                  </div>
                </div>
              ) : (
                <section className="management-editor">
                  <header>
                    <i>
                      <Building2 />
                    </i>
                    <div>
                      <span>
                        {mode === "create" ? "NEW CLIENT" : mode === "edit" ? "EDIT CLIENT" : "CLIENT DETAILS"}
                      </span>
                      <h2>{mode === "create" ? "Create client" : selected?.name}</h2>
                      <p>
                        {mode === "view"
                          ? "Review the client profile and manage its authorized contacts."
                          : "Keep client identity and contact information accurate for company operations."}
                      </p>
                    </div>
                  </header>
                  {mode === "view" && selected ? (
                    <div className="client-detail-workspace">
                      <div className="client-detail-grid">
                        {[
                          ["Client code", selected.code],
                          ["Email", selected.email || "—"],
                          ["Portal account", selected.account_email || "Not linked"],
                          ["Portal status", selected.account_status || "Pending link"],
                          ["Phone", selected.phone || "—"],
                          ["Website", selected.website || "—"],
                          ["Address", selected.address || "—"],
                          [
                            "Location",
                            [selected.city, selected.state, selected.country].filter(Boolean).join(", ") || "—",
                          ],
                          ["Status", selected.status],
                        ].map(([label, value]) => (
                          <article key={label}>
                            <span>{label}</span>
                            <strong>{value}</strong>
                          </article>
                        ))}
                      </div>
                      {renderWork?.(selected.id)}
                      {canViewPricing && (
                        <section className="client-pricing">
                          <header>
                            <div>
                              <span>Client pricing</span>
                              <h3>
                                {clientPricing?.configured_services ?? 0} Configured service
                                {(clientPricing?.configured_services ?? 0) === 1 ? "" : "s"}
                              </h3>
                            </div>
                            {selected && (
                              <button
                                type="button"
                                className="management-secondary-action"
                                onClick={() => void loadClientPricing(selected.id)}
                              >
                                <RefreshCw /> Refresh pricing
                              </button>
                            )}
                          </header>
                          {pricingError ? (
                            <div className="client-history-state error">
                              <strong>{pricingError}</strong>
                              {selected && (
                                <button type="button" onClick={() => void loadClientPricing(selected.id)}>
                                  Retry
                                </button>
                              )}
                            </div>
                          ) : pricingLoading ? (
                            <div className="client-history-state">
                              <i /> Loading client pricing…
                            </div>
                          ) : clientPricing?.items.length ? (
                            <>
                              <div className="client-pricing-list">
                                {clientPricing.items.map((item) => (
                                  <article key={item.service_id}>
                                    <div>
                                      <strong>{item.service_name}</strong>
                                      <span>
                                        {item.service_code} · {item.service_description || "Service configuration"}
                                      </span>
                                    </div>
                                    <div>
                                      <span>Pricing model</span>
                                      <strong>
                                        {pricingLabel(item.current_rate?.pricing_model ?? item.default_pricing_model)}
                                      </strong>
                                    </div>
                                    <div>
                                      <span>Current rate</span>
                                      <strong>
                                        {item.current_rate
                                          ? money(item.current_rate.amount, item.current_rate.currency)
                                          : "Not configured"}
                                      </strong>
                                    </div>
                                    <div>
                                      <span>History</span>
                                      <strong>{item.history_count} entries</strong>
                                    </div>
                                    <div className="client-pricing-actions">
                                      <button type="button" onClick={() => openPricing(item, "view")}>
                                        View details
                                      </button>
                                      {canManagePricing && item.service_status === "ACTIVE" && (
                                        <button type="button" onClick={() => openPricing(item, "edit")}>
                                          Edit pricing
                                        </button>
                                      )}
                                    </div>
                                  </article>
                                ))}
                              </div>
                              {selectedPricingItem && pricingEditorMode && (
                                <div className="client-pricing-detail">
                                  <header>
                                    <div>
                                      <span>{pricingEditorMode === "edit" ? "Update pricing" : "Pricing history"}</span>
                                      <h4>{selectedPricingItem.service_name}</h4>
                                      <p>{selectedPricingItem.service_description}</p>
                                    </div>
                                    <button
                                      type="button"
                                      className="management-secondary-action"
                                      onClick={() => {
                                        setPricingEditorMode(null);
                                        setSelectedPricingItem(null);
                                        setPricingFormError("");
                                      }}
                                    >
                                      Close
                                    </button>
                                  </header>
                                  {pricingFormError && (
                                    <div className="management-form-message">{pricingFormError}</div>
                                  )}
                                  {pricingEditorMode === "edit" ? (
                                    <form className="management-form" onSubmit={(event) => event.preventDefault()}>
                                      <label className="management-field">
                                        <span>Pricing model</span>
                                        <LooplessSelect
                                          value={pricingForm.pricing_model}
                                          options={pricingModelOptions}
                                          onValueChange={(value) =>
                                            setPricingForm((current) => ({
                                              ...current,
                                              pricing_model: value as PricingModeCode,
                                            }))
                                          }
                                          ariaLabel="Client pricing model"
                                        />
                                      </label>
                                      <label className="management-field">
                                        <span>Amount</span>
                                        <span className="management-input">
                                          <CircleDollarSign />
                                          <input
                                            type="number"
                                            min="0"
                                            step="0.01"
                                            value={pricingForm.amount}
                                            onChange={(event) =>
                                              setPricingForm((current) => ({ ...current, amount: event.target.value }))
                                            }
                                            placeholder="0.00"
                                          />
                                        </span>
                                      </label>
                                      <label className="management-field">
                                        <span>Effective from</span>
                                        <span className="management-input">
                                          <NotebookTabs />
                                          <input
                                            type="datetime-local"
                                            value={pricingForm.effective_date}
                                            onChange={(event) =>
                                              setPricingForm((current) => ({
                                                ...current,
                                                effective_date: event.target.value,
                                              }))
                                            }
                                          />
                                        </span>
                                      </label>
                                      <label className="management-field wide">
                                        <span>Pricing notes</span>
                                        <div className="management-input textarea">
                                          <textarea
                                            value={pricingForm.notes}
                                            rows={3}
                                            onChange={(event) =>
                                              setPricingForm((current) => ({ ...current, notes: event.target.value }))
                                            }
                                            placeholder="Optional client pricing notes"
                                          />
                                        </div>
                                      </label>
                                      <div className="management-form-footer">
                                        <button
                                          type="button"
                                          className="management-secondary-action"
                                          onClick={() => setPricingEditorMode("view")}
                                        >
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
                                      </div>
                                    </form>
                                  ) : null}
                                  <div className="client-pricing-history">
                                    <article>
                                      <span>Current configuration</span>
                                      <strong>
                                        {selectedPricingItem.current_rate
                                          ? `${money(selectedPricingItem.current_rate.amount, selectedPricingItem.current_rate.currency)} · ${pricingLabel(selectedPricingItem.current_rate.pricing_model)}`
                                          : `Uses ${pricingLabel(selectedPricingItem.default_pricing_model)} until configured`}
                                      </strong>
                                      <small>
                                        {selectedPricingItem.current_rate
                                          ? `Effective ${new Date(selectedPricingItem.current_rate.effective_from).toLocaleString()} by ${selectedPricingItem.current_rate.created_by_name}`
                                          : "No client-specific price exists yet for this service."}
                                      </small>
                                    </article>
                                    <div className="client-pricing-history-list">
                                      {selectedPricingItem.history.length ? (
                                        selectedPricingItem.history.map((entry) => (
                                          <article key={entry.id}>
                                            <div>
                                              <strong>{money(entry.amount, entry.currency)}</strong>
                                              <span>{pricingLabel(entry.pricing_model)}</span>
                                            </div>
                                            <div>
                                              <strong>{new Date(entry.effective_from).toLocaleString()}</strong>
                                              <span>{entry.created_by_name}</span>
                                            </div>
                                            <p>{entry.notes || "No pricing notes recorded."}</p>
                                          </article>
                                        ))
                                      ) : (
                                        <div className="client-history-state">
                                          <CircleDollarSign />
                                          <strong>No pricing history yet</strong>
                                          <span>Save the first client-specific rate to begin pricing history.</span>
                                        </div>
                                      )}
                                    </div>
                                  </div>
                                </div>
                              )}
                            </>
                          ) : (
                            <div className="client-history-state">
                              <CircleDollarSign />
                              <strong>No pricing rows available</strong>
                              <span>
                                Create services in settings first, then configure client-specific pricing here.
                              </span>
                            </div>
                          )}
                        </section>
                      )}
                      <section className="client-contacts">
                        <header>
                          <div>
                            <span>Client contacts</span>
                            <h3>
                              {selected.contacts.length} Contact{selected.contacts.length === 1 ? "" : "s"}
                            </h3>
                          </div>
                          <div className="client-detail-actions">
                            {canEdit && (
                              <button
                                type="button"
                                className="management-secondary-action"
                                onClick={() => setMode("edit")}
                              >
                                Edit client
                              </button>
                            )}
                            {canManage && !contactEditorOpen && (
                              <button
                                type="button"
                                className="management-primary-action"
                                onClick={() => openContactEditor()}
                              >
                                <Plus /> Add contact
                              </button>
                            )}
                          </div>
                        </header>
                        {contactEditorOpen ? (
                          <form className="management-form client-contact-form" onSubmit={saveContact} noValidate>
                            <div className="client-contact-form-heading">
                              <span>{editingContact ? "EDIT CONTACT" : "NEW CONTACT"}</span>
                              <h3>{editingContact ? "Update client contact" : "Add client contact"}</h3>
                              <p>Keep the contact record accurate and choose one primary contact when required.</p>
                            </div>
                            {error && <div className="management-form-message">{error}</div>}
                            {contactFields.map(({ key, label, icon: Icon }) => (
                              <label className="management-field" key={key}>
                                <span>{label}</span>
                                <span className="management-input">
                                  <Icon />
                                  <input
                                    value={String(contactForm[key])}
                                    onChange={(event) => updateContact(key, event.target.value)}
                                    onBlur={() => touchContact(key)}
                                    aria-invalid={Boolean(contactErrors[key])}
                                  />
                                </span>
                                {contactErrors[key] && <small>{contactErrors[key]}</small>}
                              </label>
                            ))}
                            <label className="management-field">
                              <span>Status</span>
                              <LooplessSelect
                                value={contactForm.status}
                                onValueChange={(value) => updateContact("status", value)}
                                ariaLabel="Contact status"
                                options={[
                                  { value: "ACTIVE", label: "Active" },
                                  { value: "INACTIVE", label: "Inactive" },
                                ]}
                              />
                            </label>
                            <div className="management-field client-primary-field">
                              <span>Primary contact</span>
                              <button
                                type="button"
                                className={`client-primary-toggle${contactForm.is_primary ? " active" : ""}`}
                                role="switch"
                                aria-checked={contactForm.is_primary}
                                onClick={() => updateContact("is_primary", !contactForm.is_primary)}
                              >
                                <span /> {contactForm.is_primary ? "Primary contact" : "Set as primary"}
                              </button>
                            </div>
                            <div className="management-form-footer">
                              <button
                                type="button"
                                className="management-secondary-action"
                                onClick={() => {
                                  setContactEditorOpen(false);
                                  setEditingContact(null);
                                  setError("");
                                }}
                              >
                                Cancel
                              </button>
                              <button className="management-primary-action" disabled={saving}>
                                {saving && <RefreshCw className="spin" />}
                                {saving ? "Saving…" : editingContact ? "Save contact" : "Add contact"}
                              </button>
                            </div>
                          </form>
                        ) : selected.contacts.length ? (
                          <div className="client-contact-list">
                            {selected.contacts.map((contact) => (
                              <article key={contact.id}>
                                <div className="client-contact-avatar">{`${contact.first_name[0] ?? ""}${contact.last_name[0] ?? ""}`}</div>
                                <div className="client-contact-identity">
                                  <strong>{`${contact.first_name} ${contact.last_name}`.trim()}</strong>
                                  <span>{contact.designation || "Client contact"}</span>
                                </div>
                                <div className="client-contact-channel">
                                  <Mail />
                                  <span>{contact.email || "No email"}</span>
                                </div>
                                <div className="client-contact-channel">
                                  <Phone />
                                  <span>{contact.phone || "No phone"}</span>
                                </div>
                                <div className="client-contact-badges">
                                  {contact.is_primary && (
                                    <em className="primary">
                                      <Star /> Primary
                                    </em>
                                  )}
                                  <em className={contact.status.toLowerCase()}>{contact.status}</em>
                                </div>
                                {canManage && (
                                  <CrudActionButtons
                                    edit={{
                                      label: `Edit ${contact.first_name}`,
                                      onClick: () => openContactEditor(contact),
                                    }}
                                  />
                                )}
                              </article>
                            ))}
                          </div>
                        ) : (
                          <div className="client-contact-empty">
                            <UserRound />
                            <strong>No contacts added</strong>
                            <span>Add an authorized contact when client communication begins.</span>
                          </div>
                        )}
                      </section>
                      {canViewHistory && (
                        <section className="client-history">
                          <header>
                            <div>
                              <span>Client history</span>
                              <h3>Notes, feedback and activity</h3>
                            </div>
                            {canEdit && historyTab !== "activity" && !historyEditor && (
                              <button
                                type="button"
                                className="management-primary-action"
                                onClick={() => openHistoryEditor(historyTab)}
                              >
                                <Plus /> Add {historyTab === "notes" ? "note" : "feedback"}
                              </button>
                            )}
                          </header>
                          <nav className="client-history-tabs" aria-label="Client history sections">
                            {[
                              { key: "notes" as const, label: "Notes", count: notes.length, icon: MessageSquareText },
                              {
                                key: "feedback" as const,
                                label: "Feedback",
                                count: feedback.length,
                                icon: MessageCircleMore,
                              },
                              { key: "activity" as const, label: "Activity", count: activities.length, icon: Activity },
                            ].map(({ key, label, count, icon: Icon }) => (
                              <button
                                key={key}
                                type="button"
                                className={historyTab === key ? "active" : undefined}
                                aria-current={historyTab === key ? "page" : undefined}
                                onClick={() => {
                                  setHistoryTab(key);
                                  closeHistoryEditor();
                                }}
                              >
                                <Icon />
                                <span>{label}</span>
                                <em>{count}</em>
                              </button>
                            ))}
                          </nav>
                          {historyEditor && historyEditor.type === historyTab && (
                            <form className="client-history-editor" onSubmit={saveHistory} noValidate>
                              <div>
                                <span>
                                  {historyEditor.id ? "EDIT" : "NEW"} {historyTab === "notes" ? "NOTE" : "FEEDBACK"}
                                </span>
                                <strong>{historyTab === "notes" ? "Internal client note" : "Client feedback"}</strong>
                              </div>
                              <label>
                                <span>{historyTab === "notes" ? "Note" : "Feedback"}</span>
                                <textarea
                                  value={historyContent}
                                  maxLength={4000}
                                  rows={4}
                                  placeholder={
                                    historyTab === "notes"
                                      ? "Add context that helps your internal team…"
                                      : "Record useful feedback received from this client…"
                                  }
                                  aria-invalid={Boolean(historyContentTouched && historyValidation(historyContent))}
                                  onChange={(event) => setHistoryContent(event.target.value)}
                                  onBlur={() => setHistoryContentTouched(true)}
                                />
                                <small>
                                  {historyContentTouched && historyValidation(historyContent)
                                    ? historyValidation(historyContent)
                                    : `${historyContent.length}/4000`}
                                </small>
                              </label>
                              <footer>
                                <button
                                  type="button"
                                  className="management-secondary-action"
                                  onClick={closeHistoryEditor}
                                >
                                  Cancel
                                </button>
                                <button className="management-primary-action" disabled={historySaving}>
                                  {historySaving && <RefreshCw className="spin" />}
                                  {historySaving ? "Saving…" : historyEditor.id ? "Save changes" : "Save"}
                                </button>
                              </footer>
                            </form>
                          )}
                          {historyErrors[historyTab] ? (
                            <div className="client-history-state error" role="alert">
                              <strong>{historyErrors[historyTab]}</strong>
                              <button type="button" onClick={() => void loadHistorySection(selected.id, historyTab)}>
                                Retry
                              </button>
                            </div>
                          ) : historyLoading[historyTab] ? (
                            <div className="client-history-state">
                              <i /> Loading {historyTab}…
                            </div>
                          ) : historyTab === "activity" ? (
                            activities.length ? (
                              <div className="client-activity-list">
                                {activities.map((item) => (
                                  <article key={item.id}>
                                    <i>
                                      <Activity />
                                    </i>
                                    <div>
                                      <strong>{item.description}</strong>
                                      <span>
                                        {item.actor_name} · {relativeTime(item.created_at)}
                                      </span>
                                    </div>
                                    <em>{item.type.replaceAll("_", " ")}</em>
                                  </article>
                                ))}
                              </div>
                            ) : (
                              <div className="client-history-state">
                                <Activity />
                                <strong>No client activity yet</strong>
                              </div>
                            )
                          ) : (historyTab === "notes" ? notes : feedback).length ? (
                            <div className="client-history-list">
                              {(historyTab === "notes" ? notes : feedback).map((item) => (
                                <article key={item.id}>
                                  <div className="client-history-avatar">
                                    {item.created_by_name
                                      .split(/\s+/)
                                      .slice(0, 2)
                                      .map((part) => part[0])
                                      .join("")}
                                  </div>
                                  <div>
                                    <header>
                                      <strong>{item.created_by_name}</strong>
                                      <span>{relativeTime(item.created_at)}</span>
                                    </header>
                                    <p>{item.content}</p>
                                  </div>
                                  {(canEdit || (historyTab === "notes" && canDelete)) && (
                                    <CrudActionButtons
                                      edit={
                                        canEdit
                                          ? {
                                              label: `Edit client ${historyTab}`,
                                              onClick: () => openHistoryEditor(historyTab, item),
                                            }
                                          : undefined
                                      }
                                      remove={
                                        historyTab === "notes" && canDelete
                                          ? {
                                              label: "Delete client note",
                                              onClick: () => setPendingNoteDelete(item),
                                            }
                                          : undefined
                                      }
                                    />
                                  )}
                                </article>
                              ))}
                            </div>
                          ) : (
                            <div className="client-history-state">
                              {historyTab === "notes" ? <MessageSquareText /> : <MessageCircleMore />}
                              <strong>No client {historyTab} yet</strong>
                              <span>
                                {historyTab === "notes"
                                  ? "Keep internal context connected to this client."
                                  : "Record feedback when the client shares it."}
                              </span>
                            </div>
                          )}
                        </section>
                      )}
                    </div>
                  ) : (
                    <form className="management-form" onSubmit={save} noValidate>
                      {error && <div className="management-form-message">{error}</div>}
                      {fields.map(({ key, label, icon: Icon, wide }) => (
                        <label className={`management-field ${wide ? "wide" : ""}`} key={key}>
                          <span>{label}</span>
                          <span className="management-input">
                            <Icon />
                            <input
                              value={form[key]}
                              onChange={(event) => update(key, event.target.value)}
                              onBlur={() => touchField(key)}
                              aria-invalid={Boolean(fieldErrors[key])}
                            />
                          </span>
                          {fieldErrors[key] && <small>{fieldErrors[key]}</small>}
                        </label>
                      ))}
                      {mode === "edit" && (
                        <label className="management-field">
                          <span>Status</span>
                          <LooplessSelect
                            value={form.status}
                            onValueChange={(value) => update("status", value)}
                            ariaLabel="Client status"
                            options={[
                              { value: "ACTIVE", label: "Active" },
                              { value: "INACTIVE", label: "Inactive" },
                            ]}
                          />
                        </label>
                      )}
                      <div className="management-form-footer">
                        <button type="button" className="management-secondary-action" onClick={backToClients}>
                          Cancel
                        </button>
                        <button className="management-primary-action" disabled={saving}>
                          {saving && <RefreshCw className="spin" />}
                          {saving ? "Saving…" : mode === "edit" ? "Save changes" : "Create client"}
                        </button>
                      </div>
                    </form>
                  )}
                </section>
              )}
            </>
          )}
        </section>
      </div>
      <ConfirmationDialog
        open={Boolean(pendingStatus)}
        title={`${pendingStatus?.status === "ACTIVE" ? "Disable" : "Enable"} this client?`}
        description="The client remains in company history while its availability changes immediately."
        confirmLabel={`${pendingStatus?.status === "ACTIVE" ? "Disable" : "Enable"} client`}
        tone={pendingStatus?.status === "ACTIVE" ? "danger" : "primary"}
        loading={saving}
        onCancel={() => setPendingStatus(null)}
        onConfirm={() => void changeStatus()}
      />
      <ConfirmationDialog
        open={Boolean(pendingDelete)}
        title="Delete this pending client?"
        description="This removes the client profile, pending invitation and unaccepted login before activation."
        confirmLabel="Delete client"
        tone="danger"
        loading={saving}
        onCancel={() => setPendingDelete(null)}
        onConfirm={() => void deleteClient()}
      />
      <ConfirmationDialog
        open={Boolean(pendingNoteDelete)}
        title="Delete this client note?"
        description="This internal note will be removed permanently. The activity timeline will retain the deletion event."
        confirmLabel="Delete note"
        tone="danger"
        loading={historySaving}
        onCancel={() => setPendingNoteDelete(null)}
        onConfirm={() => void deleteNote()}
      />
    </>
  );
}
