// Copy of frontend/shared/forms/phone-input.tsx (the Client app cannot import shared/). Keep in sync.
"use client";

/*
 * Phone number with a separate country-code box (owner request 2026-11-28: "phone number pakkana
 * country code box ... countries drop down"). The code box opens a searchable list of countries;
 * the number box stays the form's own input (passed as a render prop), so each form keeps its look.
 * The value is one string, "+91 98765 43210": the dial code, a space, then the number. A number
 * saved without a code is read as India (+91). An empty number gives "".
 *
 * The code box is a span with role="button", not a <button>: inside a <label> a button would take
 * the label's clicks away from the number box. The country list opens at page level (a portal,
 * fixed under the code box, or above it near the bottom of the screen) so a form or modal edge
 * never cuts it off and the form's input styles never reach its search box (2026-11-28).
 */
import {
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
  type KeyboardEvent,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";
import { Check, ChevronDown, Search } from "lucide-react";

type Country = { iso: string; name: string; dial: string };

// ISO code, name, dial code. Countries that share a code (+1, +7, +44 …) are all listed.
const DATA: [string, string, string][] = [
  ["IN", "India", "+91"],
  ["AF", "Afghanistan", "+93"],
  ["AL", "Albania", "+355"],
  ["DZ", "Algeria", "+213"],
  ["AD", "Andorra", "+376"],
  ["AO", "Angola", "+244"],
  ["AG", "Antigua and Barbuda", "+1"],
  ["AR", "Argentina", "+54"],
  ["AM", "Armenia", "+374"],
  ["AU", "Australia", "+61"],
  ["AT", "Austria", "+43"],
  ["AZ", "Azerbaijan", "+994"],
  ["BS", "Bahamas", "+1"],
  ["BH", "Bahrain", "+973"],
  ["BD", "Bangladesh", "+880"],
  ["BB", "Barbados", "+1"],
  ["BY", "Belarus", "+375"],
  ["BE", "Belgium", "+32"],
  ["BZ", "Belize", "+501"],
  ["BJ", "Benin", "+229"],
  ["BT", "Bhutan", "+975"],
  ["BO", "Bolivia", "+591"],
  ["BA", "Bosnia and Herzegovina", "+387"],
  ["BW", "Botswana", "+267"],
  ["BR", "Brazil", "+55"],
  ["BN", "Brunei", "+673"],
  ["BG", "Bulgaria", "+359"],
  ["BF", "Burkina Faso", "+226"],
  ["BI", "Burundi", "+257"],
  ["KH", "Cambodia", "+855"],
  ["CM", "Cameroon", "+237"],
  ["CA", "Canada", "+1"],
  ["CV", "Cape Verde", "+238"],
  ["CF", "Central African Republic", "+236"],
  ["TD", "Chad", "+235"],
  ["CL", "Chile", "+56"],
  ["CN", "China", "+86"],
  ["CO", "Colombia", "+57"],
  ["KM", "Comoros", "+269"],
  ["CG", "Congo", "+242"],
  ["CD", "Congo (DRC)", "+243"],
  ["CR", "Costa Rica", "+506"],
  ["CI", "Côte d’Ivoire", "+225"],
  ["HR", "Croatia", "+385"],
  ["CU", "Cuba", "+53"],
  ["CY", "Cyprus", "+357"],
  ["CZ", "Czechia", "+420"],
  ["DK", "Denmark", "+45"],
  ["DJ", "Djibouti", "+253"],
  ["DM", "Dominica", "+1"],
  ["DO", "Dominican Republic", "+1"],
  ["EC", "Ecuador", "+593"],
  ["EG", "Egypt", "+20"],
  ["SV", "El Salvador", "+503"],
  ["GQ", "Equatorial Guinea", "+240"],
  ["ER", "Eritrea", "+291"],
  ["EE", "Estonia", "+372"],
  ["SZ", "Eswatini", "+268"],
  ["ET", "Ethiopia", "+251"],
  ["FJ", "Fiji", "+679"],
  ["FI", "Finland", "+358"],
  ["FR", "France", "+33"],
  ["GA", "Gabon", "+241"],
  ["GM", "Gambia", "+220"],
  ["GE", "Georgia", "+995"],
  ["DE", "Germany", "+49"],
  ["GH", "Ghana", "+233"],
  ["GR", "Greece", "+30"],
  ["GD", "Grenada", "+1"],
  ["GT", "Guatemala", "+502"],
  ["GN", "Guinea", "+224"],
  ["GW", "Guinea-Bissau", "+245"],
  ["GY", "Guyana", "+592"],
  ["HT", "Haiti", "+509"],
  ["HN", "Honduras", "+504"],
  ["HK", "Hong Kong", "+852"],
  ["HU", "Hungary", "+36"],
  ["IS", "Iceland", "+354"],
  ["ID", "Indonesia", "+62"],
  ["IR", "Iran", "+98"],
  ["IQ", "Iraq", "+964"],
  ["IE", "Ireland", "+353"],
  ["IL", "Israel", "+972"],
  ["IT", "Italy", "+39"],
  ["JM", "Jamaica", "+1"],
  ["JP", "Japan", "+81"],
  ["JO", "Jordan", "+962"],
  ["KZ", "Kazakhstan", "+7"],
  ["KE", "Kenya", "+254"],
  ["KI", "Kiribati", "+686"],
  ["KW", "Kuwait", "+965"],
  ["KG", "Kyrgyzstan", "+996"],
  ["LA", "Laos", "+856"],
  ["LV", "Latvia", "+371"],
  ["LB", "Lebanon", "+961"],
  ["LS", "Lesotho", "+266"],
  ["LR", "Liberia", "+231"],
  ["LY", "Libya", "+218"],
  ["LI", "Liechtenstein", "+423"],
  ["LT", "Lithuania", "+370"],
  ["LU", "Luxembourg", "+352"],
  ["MO", "Macau", "+853"],
  ["MG", "Madagascar", "+261"],
  ["MW", "Malawi", "+265"],
  ["MY", "Malaysia", "+60"],
  ["MV", "Maldives", "+960"],
  ["ML", "Mali", "+223"],
  ["MT", "Malta", "+356"],
  ["MH", "Marshall Islands", "+692"],
  ["MR", "Mauritania", "+222"],
  ["MU", "Mauritius", "+230"],
  ["MX", "Mexico", "+52"],
  ["FM", "Micronesia", "+691"],
  ["MD", "Moldova", "+373"],
  ["MC", "Monaco", "+377"],
  ["MN", "Mongolia", "+976"],
  ["ME", "Montenegro", "+382"],
  ["MA", "Morocco", "+212"],
  ["MZ", "Mozambique", "+258"],
  ["MM", "Myanmar", "+95"],
  ["NA", "Namibia", "+264"],
  ["NR", "Nauru", "+674"],
  ["NP", "Nepal", "+977"],
  ["NL", "Netherlands", "+31"],
  ["NZ", "New Zealand", "+64"],
  ["NI", "Nicaragua", "+505"],
  ["NE", "Niger", "+227"],
  ["NG", "Nigeria", "+234"],
  ["KP", "North Korea", "+850"],
  ["MK", "North Macedonia", "+389"],
  ["NO", "Norway", "+47"],
  ["OM", "Oman", "+968"],
  ["PK", "Pakistan", "+92"],
  ["PW", "Palau", "+680"],
  ["PS", "Palestine", "+970"],
  ["PA", "Panama", "+507"],
  ["PG", "Papua New Guinea", "+675"],
  ["PY", "Paraguay", "+595"],
  ["PE", "Peru", "+51"],
  ["PH", "Philippines", "+63"],
  ["PL", "Poland", "+48"],
  ["PT", "Portugal", "+351"],
  ["PR", "Puerto Rico", "+1"],
  ["QA", "Qatar", "+974"],
  ["RO", "Romania", "+40"],
  ["RU", "Russia", "+7"],
  ["RW", "Rwanda", "+250"],
  ["KN", "Saint Kitts and Nevis", "+1"],
  ["LC", "Saint Lucia", "+1"],
  ["VC", "Saint Vincent and the Grenadines", "+1"],
  ["WS", "Samoa", "+685"],
  ["SM", "San Marino", "+378"],
  ["ST", "São Tomé and Príncipe", "+239"],
  ["SA", "Saudi Arabia", "+966"],
  ["SN", "Senegal", "+221"],
  ["RS", "Serbia", "+381"],
  ["SC", "Seychelles", "+248"],
  ["SL", "Sierra Leone", "+232"],
  ["SG", "Singapore", "+65"],
  ["SK", "Slovakia", "+421"],
  ["SI", "Slovenia", "+386"],
  ["SB", "Solomon Islands", "+677"],
  ["SO", "Somalia", "+252"],
  ["ZA", "South Africa", "+27"],
  ["KR", "South Korea", "+82"],
  ["SS", "South Sudan", "+211"],
  ["ES", "Spain", "+34"],
  ["LK", "Sri Lanka", "+94"],
  ["SD", "Sudan", "+249"],
  ["SR", "Suriname", "+597"],
  ["SE", "Sweden", "+46"],
  ["CH", "Switzerland", "+41"],
  ["SY", "Syria", "+963"],
  ["TW", "Taiwan", "+886"],
  ["TJ", "Tajikistan", "+992"],
  ["TZ", "Tanzania", "+255"],
  ["TH", "Thailand", "+66"],
  ["TL", "Timor-Leste", "+670"],
  ["TG", "Togo", "+228"],
  ["TO", "Tonga", "+676"],
  ["TT", "Trinidad and Tobago", "+1"],
  ["TN", "Tunisia", "+216"],
  ["TR", "Türkiye", "+90"],
  ["TM", "Turkmenistan", "+993"],
  ["TV", "Tuvalu", "+688"],
  ["UG", "Uganda", "+256"],
  ["UA", "Ukraine", "+380"],
  ["AE", "United Arab Emirates", "+971"],
  ["GB", "United Kingdom", "+44"],
  ["US", "United States", "+1"],
  ["UY", "Uruguay", "+598"],
  ["UZ", "Uzbekistan", "+998"],
  ["VU", "Vanuatu", "+678"],
  ["VA", "Vatican City", "+39"],
  ["VE", "Venezuela", "+58"],
  ["VN", "Vietnam", "+84"],
  ["YE", "Yemen", "+967"],
  ["ZM", "Zambia", "+260"],
  ["ZW", "Zimbabwe", "+263"],
];

export const COUNTRIES: Country[] = DATA.map(([iso, name, dial]) => ({ iso, name, dial }));
const INDIA = COUNTRIES[0];
// When several countries share a code, a saved number is shown with this one.
const PREFERRED: Record<string, string> = { "+1": "US", "+7": "RU", "+39": "IT", "+44": "GB" };
const BY_LENGTH = [...new Set(COUNTRIES.map((country) => country.dial))].sort((a, b) => b.length - a.length);

function flag(iso: string): string {
  return String.fromCodePoint(...[...iso.toUpperCase()].map((letter) => 0x1f1e6 + letter.charCodeAt(0) - 65));
}

function countryFor(dial: string): Country {
  const preferred = PREFERRED[dial];
  return (
    COUNTRIES.find((country) => country.dial === dial && (!preferred || country.iso === preferred)) ??
    COUNTRIES.find((country) => country.dial === dial) ??
    INDIA
  );
}

/** "+91 98765 43210" -> India and "98765 43210". No code -> India. */
export function splitPhone(value: string | null | undefined): { country: Country; number: string; coded: boolean } {
  const text = (value ?? "").trimStart();
  if (text.startsWith("+")) {
    const dial = BY_LENGTH.find((code) => text.startsWith(code));
    if (dial) return { country: countryFor(dial), number: text.slice(dial.length).trimStart(), coded: true };
  }
  return { country: INDIA, number: text, coded: false };
}

export function joinPhone(country: Country, number: string): string {
  return number.trim() ? `${country.dial} ${number.trimStart()}` : "";
}

export type PhoneNumberInputProps = {
  value: string;
  onChange: (event: ChangeEvent<HTMLInputElement>) => void;
  type: "tel";
  inputMode: "tel";
  autoComplete: "tel-national";
};

export function PhoneInput({
  value,
  onChange,
  children,
  disabled = false,
  className = "",
}: {
  value: string | null | undefined;
  onChange: (value: string) => void;
  /** Renders the number box with these props, inside the form's own field styling. */
  children: (input: PhoneNumberInputProps) => ReactNode;
  disabled?: boolean;
  className?: string;
}) {
  const parsed = splitPhone(value);
  const [country, setCountry] = useState<Country>(parsed.country);
  // A new value from outside (a record loaded, a form reset) brings its own code.
  const [seen, setSeen] = useState(value ?? "");
  if ((value ?? "") !== seen) {
    setSeen(value ?? "");
    if (parsed.coded && parsed.country.dial !== country.dial) setCountry(parsed.country);
  }

  const choose = (next: Country) => {
    setCountry(next);
    if (parsed.number.trim()) onChange(joinPhone(next, parsed.number));
  };

  return (
    <span className={`phone-field ${className}`.trim()}>
      <CountryCodePicker country={country} onChoose={choose} disabled={disabled} />
      <span className="phone-field-number">
        {children({
          value: parsed.number,
          onChange: (event) => onChange(joinPhone(country, event.target.value)),
          type: "tel",
          inputMode: "tel",
          autoComplete: "tel-national",
        })}
      </span>
      <style>{PHONE_STYLES}</style>
    </span>
  );
}

type MenuPlace = { left: number; width: number; top?: number; bottom?: number };

/** Under the code box, or above it when there is more room there. */
function menuPlace(anchor: HTMLElement | null): MenuPlace | null {
  const box = anchor?.getBoundingClientRect();
  if (!box) return null;
  const width = Math.min(300, window.innerWidth - 32);
  const left = Math.max(16, Math.min(box.left, window.innerWidth - width - 16));
  const below = window.innerHeight - box.bottom;
  return below >= 330 || below >= box.top
    ? { left, width, top: box.bottom + 7 }
    : { left, width, bottom: window.innerHeight - box.top + 7 };
}

function CountryCodePicker({
  country,
  onChoose,
  disabled,
}: {
  country: Country;
  onChoose: (country: Country) => void;
  disabled: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [active, setActive] = useState(0);
  const root = useRef<HTMLSpanElement>(null);
  const menu = useRef<HTMLSpanElement>(null);
  const [place, setPlace] = useState<MenuPlace | null>(null);
  const searchBox = useRef<HTMLInputElement>(null);
  const list = useRef<HTMLSpanElement>(null);
  const listId = useId();

  const matches = useMemo(() => {
    const needle = search.trim().toLowerCase().replace(/^\+/, "");
    if (!needle) return COUNTRIES;
    return COUNTRIES.filter(
      (item) =>
        item.name.toLowerCase().includes(needle) ||
        item.dial.slice(1).startsWith(needle) ||
        item.iso.toLowerCase() === needle,
    );
  }, [search]);

  useEffect(() => {
    if (!open) return;
    const close = (event: PointerEvent) => {
      const target = event.target as Node;
      if (!root.current?.contains(target) && !menu.current?.contains(target)) setOpen(false);
    };
    const follow = () => setPlace(menuPlace(root.current));
    document.addEventListener("pointerdown", close);
    window.addEventListener("resize", follow);
    window.addEventListener("scroll", follow, true);
    searchBox.current?.focus();
    return () => {
      document.removeEventListener("pointerdown", close);
      window.removeEventListener("resize", follow);
      window.removeEventListener("scroll", follow, true);
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    list.current?.querySelector<HTMLElement>(`[data-index="${active}"]`)?.scrollIntoView({ block: "nearest" });
  }, [active, open]);

  const show = () => {
    if (disabled) return;
    setSearch("");
    setActive(Math.max(0, COUNTRIES.indexOf(country)));
    setPlace(menuPlace(root.current));
    setOpen(true);
  };
  const pick = (item: Country | undefined) => {
    if (item) onChoose(item);
    setOpen(false);
  };
  const onKeys = (event: KeyboardEvent<HTMLElement>) => {
    if (event.key === "Escape") {
      event.preventDefault();
      setOpen(false);
    } else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      if (!open) return show();
      const step = event.key === "ArrowDown" ? 1 : -1;
      setActive((index) => (index + step + matches.length) % Math.max(1, matches.length));
    } else if (event.key === "Enter") {
      // Never submit the form from here.
      event.preventDefault();
      if (open) pick(matches[active]);
      else show();
    } else if (event.key === " " && !open) {
      event.preventDefault();
      show();
    }
  };

  return (
    <span className={`phone-code${open ? " open" : ""}${disabled ? " disabled" : ""}`} ref={root}>
      <span
        role="button"
        tabIndex={disabled ? -1 : 0}
        className="phone-code-button"
        aria-label={`Country code ${country.dial}, ${country.name}`}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={listId}
        aria-disabled={disabled}
        onClick={(event) => {
          event.preventDefault();
          if (open) setOpen(false);
          else show();
        }}
        onKeyDown={onKeys}
      >
        <span className="phone-code-flag" aria-hidden="true">
          {flag(country.iso)}
        </span>
        <span>{country.dial}</span>
        <ChevronDown aria-hidden="true" />
      </span>
      {open &&
        place &&
        createPortal(
          <span
            className="phone-code-menu"
            ref={menu}
            style={{ left: place.left, width: place.width, top: place.top, bottom: place.bottom }}
            onClick={(event) => event.preventDefault()}
          >
            <span className="phone-code-search">
              <Search aria-hidden="true" />
              <input
                ref={searchBox}
                value={search}
                placeholder="Search country or code"
                aria-label="Search country or code"
                aria-controls={listId}
                autoComplete="off"
                onChange={(event) => {
                  setSearch(event.target.value);
                  setActive(0);
                }}
                onKeyDown={onKeys}
              />
            </span>
            <span id={listId} role="listbox" aria-label="Country code" ref={list}>
              {matches.length === 0 ? (
                <span className="phone-code-empty">No country found</span>
              ) : (
                matches.map((item, index) => (
                  <button
                    type="button"
                    role="option"
                    key={item.iso}
                    data-index={index}
                    aria-selected={item.iso === country.iso}
                    className={index === active ? "active" : undefined}
                    onPointerMove={() => setActive(index)}
                    onClick={() => pick(item)}
                  >
                    <span className="phone-code-flag" aria-hidden="true">
                      {flag(item.iso)}
                    </span>
                    <span className="phone-code-name">{item.name}</span>
                    <span className="phone-code-dial">{item.dial}</span>
                    {item.iso === country.iso && <Check aria-hidden="true" />}
                  </button>
                ))
              )}
            </span>
          </span>,
          document.body,
        )}
    </span>
  );
}

const PHONE_STYLES = `
.phone-field {
  display: flex;
  align-items: stretch;
  gap: 8px;
  min-width: 0;
}
.phone-field-number {
  flex: 1;
  min-width: 0;
  display: flex;
}
.phone-field-number > * {
  flex: 1;
  min-width: 0;
}
.phone-code {
  position: relative;
  flex: 0 0 auto;
  display: flex;
}
.phone-code-button {
  min-height: 42px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 0 10px;
  border: 1px solid var(--border, #e2e8f0);
  border-radius: 10px;
  color: var(--foreground, #0f172a);
  background: var(--surface, #ffffff);
  font: 600 0.78rem/1 var(--font-poppins), "Poppins", Arial, sans-serif;
  white-space: nowrap;
  cursor: pointer;
  user-select: none;
}
.phone-code.disabled .phone-code-button {
  opacity: 0.55;
  cursor: not-allowed;
}
.phone-code.open .phone-code-button,
.phone-code:not(.disabled) .phone-code-button:hover,
.phone-code-button:focus-visible {
  border-color: #0876ed;
  box-shadow: 0 0 0 3px #0876ed16;
  outline: none;
}
.phone-code-button svg {
  width: 15px;
  height: 15px;
  color: #0876ed;
  transition: transform 0.15s ease;
}
.phone-code.open .phone-code-button svg {
  transform: rotate(180deg);
}
.phone-code-flag {
  font-size: 1rem;
  line-height: 1;
}
.phone-code-menu {
  position: fixed;
  z-index: 2000;
  display: grid;
  gap: 6px;
  padding: 8px;
  border: 1px solid var(--border, #e2e8f0);
  border-radius: 12px;
  color: var(--foreground, #0f172a);
  background: var(--surface, #ffffff);
  box-shadow: 0 18px 40px rgba(15, 23, 42, 0.16);
}
.phone-code-search {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 10px;
  border: 1px solid var(--border, #e2e8f0);
  border-radius: 9px;
}
.phone-code-search svg {
  width: 15px;
  height: 15px;
  color: var(--muted, #64748b);
}
.phone-code-menu .phone-code-search input {
  width: 100%;
  min-height: 36px;
  margin: 0;
  padding: 0;
  border: 0 !important;
  border-radius: 0;
  outline: 0 !important;
  box-shadow: none !important;
  color: inherit;
  background: transparent !important;
  font: 500 0.78rem/1.2 var(--font-poppins), "Poppins", Arial, sans-serif;
}
.phone-code-menu [role="listbox"] {
  max-height: 240px;
  overflow: auto;
  display: grid;
  gap: 2px;
}
.phone-code-menu [role="option"] {
  display: grid;
  grid-template-columns: 22px minmax(0, 1fr) auto 16px;
  align-items: center;
  gap: 8px;
  min-height: 36px;
  padding: 0 8px;
  border: 0;
  border-radius: 8px;
  color: inherit;
  background: transparent;
  font: 500 0.76rem/1.2 var(--font-poppins), "Poppins", Arial, sans-serif;
  text-align: left;
  cursor: pointer;
}
.phone-code-menu [role="option"].active,
.phone-code-menu [role="option"][aria-selected="true"] {
  background: color-mix(in srgb, #0876ed 10%, transparent);
}
.phone-code-menu [role="option"] svg {
  width: 15px;
  height: 15px;
  color: #0876ed;
}
.phone-code-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.phone-code-dial {
  color: var(--muted, #64748b);
  font-weight: 600;
}
.phone-code-empty {
  padding: 10px 8px;
  color: var(--muted, #64748b);
  font-size: 0.76rem;
}
`;
