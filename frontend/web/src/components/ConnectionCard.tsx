import type { ReactNode } from "react";

/** Shared summary presentation for cabinet connections and pathway cable inspection. */
export function ConnectionCard({
  title, metric, subtitle, cableTypeCounts, status, actions, children,
  className = "", formatNumber = value => value.toLocaleString(), onViewCableType,
}: {
  title: ReactNode;
  metric: ReactNode;
  subtitle?: ReactNode;
  cableTypeCounts: Record<string, number>;
  status?: ReactNode;
  actions?: ReactNode;
  children?: ReactNode;
  className?: string;
  formatNumber?: (value: number) => string;
  onViewCableType?: (type: string) => void;
}) {
  return <article className={`connection-item ${className}`.trim()}>
    <div className="connection-heading"><strong>{title}</strong>{metric}</div>
    {status}
    {subtitle && <div className="connection-meta">{subtitle}</div>}
    <ul className={`cable-types${onViewCableType ? " cable-types-with-actions" : ""}`}>
      {Object.entries(cableTypeCounts).map(([type, count]) => <li key={type}><span>{type}</span><b>{formatNumber(count)}</b>
        {onViewCableType && <button className="mini-detail-button" aria-label={`View ${type} cable details${typeof title === "string" ? ` · ${title}` : ""}`} onClick={() => onViewCableType(type)}>View cables</button>}
      </li>)}
    </ul>
    {actions}
    {children}
  </article>;
}
