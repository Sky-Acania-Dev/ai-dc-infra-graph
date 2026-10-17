import type { ReactNode } from "react";

/** Shared summary presentation for cabinet connections and pathway cable inspection. */
export function ConnectionCard({
  title, metric, subtitle, cableTypeCounts, status, actions, children,
  className = "", formatNumber = value => value.toLocaleString(),
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
}) {
  return <article className={`connection-item ${className}`.trim()}>
    <div className="connection-heading"><strong>{title}</strong>{metric}</div>
    {status}
    {subtitle && <div className="connection-meta">{subtitle}</div>}
    <ul className="cable-types">
      {Object.entries(cableTypeCounts).map(([type, count]) => <li key={type}><span>{type}</span><b>{formatNumber(count)}</b></li>)}
    </ul>
    {actions}
    {children}
  </article>;
}
