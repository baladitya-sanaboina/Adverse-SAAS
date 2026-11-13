import { Eye, LoaderCircle, Pencil, Power, Trash2, type LucideIcon } from "lucide-react";
import "@/styles/crud-action-buttons.css";

type Action = {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  loading?: boolean;
  icon?: LucideIcon;
};

export function CrudActionButtons({
  view,
  edit,
  toggle,
  remove,
  active = true,
}: {
  view?: Action;
  edit?: Action;
  toggle?: Action;
  remove?: Action;
  active?: boolean;
}) {
  const ViewIcon = view?.icon ?? Eye;

  return (
    <div className="crud-actions" aria-label="Row actions">
      {view && (
        <button
          type="button"
          title={view.label}
          aria-label={view.label}
          onClick={view.onClick}
          disabled={view.disabled}
        >
          {view.loading ? <LoaderCircle className="crud-action-spinner" /> : <ViewIcon />}
        </button>
      )}
      {edit && (
        <button
          type="button"
          title={edit.label}
          aria-label={edit.label}
          onClick={edit.onClick}
          disabled={edit.disabled}
        >
          {edit.loading ? <LoaderCircle className="crud-action-spinner" /> : <Pencil />}
        </button>
      )}
      {toggle && (
        <button
          type="button"
          className={active ? "danger" : "success"}
          title={toggle.label}
          aria-label={toggle.label}
          onClick={toggle.onClick}
          disabled={toggle.disabled}
        >
          <Power />
        </button>
      )}
      {remove && (
        <button
          type="button"
          className="danger"
          title={remove.label}
          aria-label={remove.label}
          onClick={remove.onClick}
          disabled={remove.disabled}
        >
          <Trash2 />
        </button>
      )}
    </div>
  );
}
