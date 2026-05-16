import { ChevronDown } from "lucide-react";
import { type ReactNode, useState } from "react";

export type IdentityMetaItem = {
  label: string;
  value: ReactNode;
};

export type ImpactTone = "neutral" | "good" | "warning" | "danger";

export type ImpactItem = {
  label: string;
  value: ReactNode;
  tone?: ImpactTone;
};

type ProjectIdentityBarProps = {
  eyebrow: string;
  title: string;
  meta: IdentityMetaItem[];
  actions?: ReactNode;
};

export function ProjectIdentityBar({ eyebrow, title, meta, actions }: ProjectIdentityBarProps) {
  return (
    <header className="guided-identity" role="banner">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
      </div>
      <dl className="guided-identity__meta">
        {meta.map((item) => (
          <div key={item.label}>
            <dt>{item.label}</dt>
            <dd>{item.value}</dd>
          </div>
        ))}
      </dl>
      {actions ? <div className="guided-identity__actions">{actions}</div> : null}
    </header>
  );
}

type ImpactPanelProps = {
  title: string;
  items: ImpactItem[];
};

export function ImpactPanel({ title, items }: ImpactPanelProps) {
  return (
    <section className="impact-panel" aria-label={title}>
      <h2>{title}</h2>
      <div className="impact-panel__grid">
        {items.map((item) => (
          <article className={`impact-item impact-item--${item.tone ?? "neutral"}`} key={item.label}>
            <span>{item.label}</span>
            <strong>{item.value}</strong>
          </article>
        ))}
      </div>
    </section>
  );
}

type PrimaryActionPanelProps = {
  eyebrow: string;
  title: string;
  summary: ReactNode;
  action: ReactNode;
  impact: ReactNode;
  children?: ReactNode;
};

export function PrimaryActionPanel({
  eyebrow,
  title,
  summary,
  action,
  impact,
  children,
}: PrimaryActionPanelProps) {
  return (
    <section className="primary-action-panel" aria-labelledby="primary-action-title">
      <div className="primary-action-panel__main">
        <p className="eyebrow">{eyebrow}</p>
        <h2 id="primary-action-title">{title}</h2>
        <div className="primary-action-panel__summary">{summary}</div>
        <div className="primary-action-panel__action">{action}</div>
        {children}
      </div>
      <div className="primary-action-panel__impact">{impact}</div>
    </section>
  );
}

type AdvancedDisclosureProps = {
  title: string;
  children: ReactNode;
  defaultOpen?: boolean;
};

export function AdvancedDisclosure({ title, children, defaultOpen = false }: AdvancedDisclosureProps) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <section className="advanced-disclosure">
      <button
        aria-expanded={open}
        className="advanced-disclosure__toggle"
        type="button"
        onClick={() => setOpen((current) => !current)}
      >
        <span>{title}</span>
        <ChevronDown aria-hidden="true" className={open ? "is-open" : ""} size={18} />
      </button>
      {open ? <div className="advanced-disclosure__content">{children}</div> : null}
    </section>
  );
}
