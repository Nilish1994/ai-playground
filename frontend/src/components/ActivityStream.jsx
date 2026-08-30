import StatusBadge from "./StatusBadge.jsx";

function formatTime(value) {
  return new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(new Date(value));
}

export default function ActivityStream({ events }) {
  return (
    <section className="activity" aria-labelledby="activity-title">
      <header className="section-heading">
        <h2 id="activity-title">Activity Log</h2>
        <span>{events.length} events</span>
      </header>
      <ol>
        {events.map((event) => (
          <li key={`${event.projectId}-${event.id}`}>
            <time dateTime={event.time}>{formatTime(event.time)}</time>
            <StatusBadge status={event.status} />
            <span className="activity-project">{event.projectName}</span>
            <span>{event.message}</span>
          </li>
        ))}
      </ol>
    </section>
  );
}
