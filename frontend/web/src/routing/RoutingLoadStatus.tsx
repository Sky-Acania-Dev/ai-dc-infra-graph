export function RoutingLoadStatus({layoutLoading=false,loading,hasRoutes,error,onRetry}: {
  layoutLoading?:boolean;loading:boolean;hasRoutes:boolean;error:string;onRetry:()=>void;
}) {
  const pending=layoutLoading || loading;
  if (!pending && !error) return null;
  const title=layoutLoading ? "Loading routing layout…" : pending ? hasRoutes ? "Updating cable routes…" : "Loading cable route data…"
    : hasRoutes ? "Showing saved cable routes" : "Cable route data could not be loaded";
  const detail=layoutLoading ? "Preparing the pathway map before loading cable routes and counts."
    : pending ? hasRoutes ? "Saved routes remain visible while current routes and counts are checked. Route editing waits for current data."
      : "The cabinet map is available. Cable routes and counts are still loading."
    : hasRoutes ? "Current data could not be checked. You can inspect saved routes; route editing is unavailable until loading succeeds."
      : "The cabinet map is available. Retry to load cable routes and counts.";
  return <div className={`routing-load-status ${pending ? "is-loading" : "has-error"}`} role="status" aria-live="polite" aria-atomic="true">
    {pending && <span className="map-loading-spinner" aria-hidden="true" />}
    <div><strong>{title}</strong><span>{detail}</span></div>
    {!pending && <button type="button" onClick={onRetry}>Retry loading</button>}
  </div>;
}
