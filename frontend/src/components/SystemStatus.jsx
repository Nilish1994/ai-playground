function formatBytes(value) {
  if (!Number.isFinite(value)) return "—";
  return `${(value / 1024 ** 3).toFixed(1)} GB`;
}

function formatUptime(seconds) {
  if (!Number.isFinite(seconds)) return "—";
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (days) return `${days}d ${hours}h`;
  if (hours) return `${hours}h ${minutes}m`;
  return `${minutes}m`;
}

function displayHealth(status) {
  return status ? status.charAt(0) + status.slice(1).toLowerCase() : "Unknown";
}

export default function SystemStatus({ status, error, isLoading }) {
  if (isLoading && !status) {
    return <p className="system-message">&gt; loading VPS telemetry…</p>;
  }
  if (!status) {
    return <p className="system-error">! {error || "System telemetry unavailable."}</p>;
  }

  const running = status.containers.filter((container) => container.status === "running").length;
  const unhealthy = status.containers.filter(
    (container) => container.status !== "running" || container.health === "unhealthy",
  ).length;

  return (
    <section className="vps-overview" aria-label="VPS system status">
      <header>
        <h2>SYSTEM</h2>
        <span className={`system-health system-health-${status.status.toLowerCase()}`}>
          <i aria-hidden="true" /> {status.status}
        </span>
      </header>

      {error && <p className="telemetry-warning">Last refresh failed; showing previous values.</p>}
      <div className="system-columns">
        <dl className="vps-metrics">
          <dt>VPS</dt><dd>{status.vps.hostname}</dd>
          <dt>Uptime</dt><dd>{formatUptime(status.vps.uptime_seconds)}</dd>
          <dt>CPU</dt><dd>{status.vps.cpu_percent.toFixed(1)}%</dd>
          <dt>RAM</dt><dd>{formatBytes(status.vps.memory.used_bytes)} / {formatBytes(status.vps.memory.total_bytes)}</dd>
          <dt>Disk</dt><dd>{formatBytes(status.vps.disk.used_bytes)} / {formatBytes(status.vps.disk.total_bytes)}</dd>
        </dl>

        <div>
          <h3>SERVICES</h3>
          <dl className="service-list">
            {status.services.map((service) => (
              <div key={service.name}>
                <dt>{service.name}</dt>
                <dd className={`service-${service.status.toLowerCase()}`}>
                  {displayHealth(service.status)}
                </dd>
              </div>
            ))}
          </dl>
        </div>

        <div className="container-summary">
          <h3>CONTAINERS</h3>
          {status.docker_available ? (
            <p><strong>{running}</strong> running<br /><strong>{unhealthy}</strong> unhealthy/stopped</p>
          ) : (
            <p>Docker status unavailable</p>
          )}
        </div>
      </div>
    </section>
  );
}

export function ContainerDetails({ status }) {
  if (!status) return null;
  return (
    <section className="container-details">
      <h3>CONTAINER STATUS</h3>
      {!status.docker_available ? <p>Docker telemetry is unavailable.</p> : (
        <div className="container-table" role="table" aria-label="Container details">
          {status.containers.map((container) => (
            <div key={container.name} role="row">
              <span role="cell">{container.name}</span>
              <span role="cell">{container.status}</span>
              <span role="cell">{container.health || "not configured"}</span>
              <time role="cell">{container.started_at ? new Date(container.started_at).toLocaleString() : "—"}</time>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
