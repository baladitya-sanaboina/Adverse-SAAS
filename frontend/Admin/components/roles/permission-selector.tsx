"use client";

import { useState } from "react";
import { Check, ShieldCheck } from "lucide-react";

export type PermissionAction = { code: string; name: string; key: string };
export type PermissionModule = { code: string; name: string; actions: PermissionAction[] };

export function PermissionSelector({
  modules,
  selected,
  onChange,
  disabled = false,
}: {
  modules: PermissionModule[];
  selected: string[];
  onChange: (permissions: string[]) => void;
  disabled?: boolean;
}) {
  const [activeModule, setActiveModule] = useState(modules[0]?.code ?? "");
  const selectedSet = new Set(selected);
  const visibleModule = modules.find((module) => module.code === activeModule) ?? modules[0];

  const toggle = (key: string) =>
    onChange(selectedSet.has(key) ? selected.filter((item) => item !== key) : [...selected, key]);
  const toggleModule = (module: PermissionModule) => {
    const keys = module.actions.map((action) => action.key);
    const allSelected = keys.every((key) => selectedSet.has(key));
    onChange(allSelected ? selected.filter((key) => !keys.includes(key)) : [...new Set([...selected, ...keys])]);
  };

  return (
    <section className="permission-selector" aria-label="Role permissions">
      <header>
        <div>
          <i>
            <ShieldCheck aria-hidden="true" />
          </i>
          <span>
            <strong>Role access</strong>
            <small>Select a module, then choose only the actions this role needs.</small>
          </span>
        </div>
        <em>{selected.length} assigned</em>
      </header>
      <div className="permission-selector-picker">
        <nav aria-label="Permission modules">
          {modules.map((module) => {
            const selectedCount = module.actions.filter((action) => selectedSet.has(action.key)).length;
            return (
              <button
                type="button"
                key={module.code}
                className={visibleModule?.code === module.code ? "active" : ""}
                onClick={() => setActiveModule(module.code)}
              >
                <span>{module.name}</span>
                <em>
                  {selectedCount}/{module.actions.length}
                </em>
              </button>
            );
          })}
        </nav>
        {visibleModule && (
          <section className="permission-selector-actions">
            <header>
              <div>
                <strong>{visibleModule.name}</strong>
                <span>Allowed actions</span>
              </div>
              <button type="button" onClick={() => toggleModule(visibleModule)} disabled={disabled}>
                Toggle all
              </button>
            </header>
            <fieldset disabled={disabled}>
              {visibleModule.actions.map((action) => {
                const checked = selectedSet.has(action.key);
                return (
                  <label className={checked ? "selected" : ""} key={action.key}>
                    <input type="checkbox" checked={checked} onChange={() => toggle(action.key)} />
                    <i aria-hidden="true">{checked && <Check />}</i>
                    <span>{action.name}</span>
                  </label>
                );
              })}
            </fieldset>
          </section>
        )}
      </div>
    </section>
  );
}
