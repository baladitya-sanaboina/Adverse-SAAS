"use client";

import { useEffect, useId, useRef, useState } from "react";
import { Check, ChevronDown } from "lucide-react";

export type LooplessSelectOption = { value: string; label: string };
export function LooplessSelect({
  value,
  options,
  onValueChange,
  ariaLabel,
  disabled = false,
}: {
  value: string;
  options: readonly LooplessSelectOption[];
  onValueChange: (value: string) => void;
  ariaLabel: string;
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false),
    [active, setActive] = useState(0);
  const root = useRef<HTMLDivElement>(null),
    listId = useId();
  const selectedIndex = options.findIndex((option) => option.value === value);
  useEffect(() => {
    const close = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", close);
    return () => document.removeEventListener("pointerdown", close);
  }, []);
  const show = () => {
    if (!disabled) {
      setActive(selectedIndex < 0 ? 0 : selectedIndex);
      setOpen(true);
    }
  };
  const choose = (index: number) => {
    if (options[index]) onValueChange(options[index].value);
    setOpen(false);
  };
  return (
    <div className={`loopless-select ${open ? "open" : ""}`} ref={root}>
      <button
        type="button"
        aria-label={ariaLabel}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={listId}
        disabled={disabled}
        onClick={() => (open ? setOpen(false) : show())}
        onKeyDown={(event) => {
          if (event.key === "Escape") setOpen(false);
          if (event.key === "ArrowDown" || event.key === "ArrowUp") {
            event.preventDefault();
            if (!open) return show();
            setActive((index) =>
              event.key === "ArrowDown" ? (index + 1) % options.length : (index - 1 + options.length) % options.length,
            );
          }
          if ((event.key === "Enter" || event.key === " ") && open) {
            event.preventDefault();
            choose(active);
          }
        }}
      >
        <span>{options[selectedIndex]?.label ?? "Select an option"}</span>
        <ChevronDown />
      </button>
      {open && (
        <div id={listId} role="listbox" aria-label={ariaLabel}>
          {options.map((option, index) => (
            <button
              type="button"
              role="option"
              aria-selected={option.value === value}
              className={index === active ? "active" : ""}
              key={option.value}
              onPointerMove={() => setActive(index)}
              onClick={() => choose(index)}
            >
              <span>{option.label}</span>
              {option.value === value && <Check />}
            </button>
          ))}
        </div>
      )}
      <style jsx>{`
        .loopless-select {
          position: relative;
          min-width: 150px;
          color: var(--foreground);
          font-family: var(--font-poppins), Arial, sans-serif;
        }
        .loopless-select > button {
          width: 100%;
          min-height: 42px;
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
          padding: 0 13px;
          border: 1px solid var(--border);
          border-radius: 10px;
          color: var(--foreground);
          background: var(--surface);
          font:
            600 0.74rem/1.2 var(--font-poppins),
            Arial,
            sans-serif;
          text-align: left;
          cursor: pointer;
        }
        .loopless-select.open > button,
        .loopless-select > button:hover {
          border-color: #0876ed;
          box-shadow: 0 0 0 3px #0876ed16;
        }
        .loopless-select > button:disabled {
          opacity: 0.55;
          cursor: not-allowed;
        }
        .loopless-select > button :global(svg) {
          width: 17px;
          color: #0876ed;
        }
        .loopless-select.open > button :global(svg) {
          transform: rotate(180deg);
        }
        .loopless-select > div {
          position: absolute;
          z-index: 120;
          top: calc(100% + 7px);
          left: 0;
          width: max(100%, 190px);
          max-height: 260px;
          overflow: auto;
          padding: 6px;
          border: 1px solid var(--border);
          border-radius: 12px;
          background: var(--surface);
          box-shadow: 0 18px 42px #25172f24;
        }
        .loopless-select > div > button {
          width: 100%;
          min-height: 38px;
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 0 10px;
          border: 0;
          border-radius: 8px;
          color: var(--foreground);
          background: transparent;
          font:
            500 0.73rem var(--font-poppins),
            Arial,
            sans-serif;
          text-align: left;
          cursor: pointer;
        }
        .loopless-select > div > button:hover,
        .loopless-select > div > button.active {
          color: #065ec1;
          background: var(--surface-muted);
        }
        .loopless-select > div > button :global(svg) {
          width: 16px;
          color: #0876ed;
        }
        @media (max-width: 700px) {
          .loopless-select,
          .loopless-select > div {
            width: 100%;
          }
        }
      `}</style>
    </div>
  );
}
