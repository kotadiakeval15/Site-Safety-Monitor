import type { ReactNode } from "react";
import { X } from "lucide-react";

export function Spinner() {
  return <span className="spinner" aria-label="loading" />;
}

export function Loading({ label = "Loading..." }: { label?: string }) {
  return (
    <div className="center-box">
      <div style={{ display: "grid", placeItems: "center", gap: 12 }}>
        <Spinner />
        <span className="helper-text">{label}</span>
      </div>
    </div>
  );
}

export function Card({
  title,
  actions,
  children,
  bodyClass,
}: {
  title?: string;
  actions?: ReactNode;
  children: ReactNode;
  bodyClass?: string;
}) {
  return (
    <section className="card">
      {(title || actions) && (
        <div className="card__header">
          {title ? <h3>{title}</h3> : <span />}
          {actions}
        </div>
      )}
      <div className={bodyClass ?? "card__body"}>{children}</div>
    </section>
  );
}

type BadgeVariant = "neutral" | "primary" | "success" | "warning" | "danger";

export function Badge({ children, variant = "neutral" }: { children: ReactNode; variant?: BadgeVariant }) {
  return <span className={`badge badge-${variant}`}>{children}</span>;
}

const SEVERITY_VARIANT: Record<string, BadgeVariant> = {
  level_1: "success",
  level_2: "warning",
  danger: "danger",
};

export function SeverityBadge({ value }: { value: string }) {
  const label = { level_1: "Level 1", level_2: "Level 2", danger: "Danger" }[value] ?? value;
  return <Badge variant={SEVERITY_VARIANT[value] ?? "neutral"}>{label}</Badge>;
}

const STATUS_VARIANT: Record<string, BadgeVariant> = {
  active: "success",
  starting: "warning",
  inactive: "neutral",
  error: "danger",
};

export function StatusBadge({ value }: { value: string }) {
  return <Badge variant={STATUS_VARIANT[value] ?? "neutral"}>{value}</Badge>;
}

export function StatCard({
  label,
  value,
  icon,
  tone = "primary",
}: {
  label: string;
  value: ReactNode;
  icon: ReactNode;
  tone?: "primary" | "danger" | "warning" | "success";
}) {
  return (
    <div className="stat">
      <div className="stat__top">
        <span className="stat__label">{label}</span>
        <span className={`stat__icon is-${tone}`}>{icon}</span>
      </div>
      <span className="stat__value">{value}</span>
    </div>
  );
}

export function Modal({
  title,
  onClose,
  children,
  footer,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
}) {
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal__header">
          <h3>{title}</h3>
          <button className="icon-btn" onClick={onClose} aria-label="Close">
            <X size={18} />
          </button>
        </div>
        <div className="modal__body">{children}</div>
        {footer && <div className="modal__footer">{footer}</div>}
      </div>
    </div>
  );
}

export function EmptyRow({ colSpan, label }: { colSpan: number; label: string }) {
  return (
    <tr>
      <td colSpan={colSpan}>
        <div className="table-empty">{label}</div>
      </td>
    </tr>
  );
}

export function Pagination({
  page,
  totalPages,
  totalItems,
  onChange,
}: {
  page: number;
  totalPages: number;
  totalItems: number;
  onChange: (page: number) => void;
}) {
  return (
    <div className="pagination">
      <span>
        Page {page} of {Math.max(totalPages, 1)} · {totalItems} total
      </span>
      <div className="pagination__controls">
        <button className="btn btn-ghost btn-sm" disabled={page <= 1} onClick={() => onChange(page - 1)}>
          Previous
        </button>
        <button
          className="btn btn-ghost btn-sm"
          disabled={page >= totalPages}
          onClick={() => onChange(page + 1)}
        >
          Next
        </button>
      </div>
    </div>
  );
}

export function formatDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}
