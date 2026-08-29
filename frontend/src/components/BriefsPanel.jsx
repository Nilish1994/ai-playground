import StatusBadge from "./StatusBadge.jsx";

export default function BriefsPanel({ project }) {
  const currentTask = project.tasks.find((task) => task.status === "RUNNING");

  return (
    <section className="brief-console" aria-label={`${project.name} current work and briefs`}>
      <div className="section-heading">
        <h2>NOW</h2>
        <span>{project.name}</span>
      </div>
      <dl className="now-details">
        <dt>current task</dt>
        <dd>{currentTask?.title || project.currentTask}</dd>
        <dt>agent</dt>
        <dd>{currentTask?.agent || project.agent || "none"}</dd>
      </dl>

      <div className="section-heading briefs-heading">
        <h2>RECENT BRIEFS</h2>
        <span>{project.briefs.length} stored</span>
      </div>
      {project.briefs.length ? (
        <ol className="brief-list">
          {project.briefs.slice(0, 6).map((brief) => {
            const linkedTask = project.tasks.find((task) => task.id === brief.taskId);
            return (
              <li key={brief.id}>
                <div className="brief-title">
                  <StatusBadge status={brief.status} />
                  <strong>{brief.title}</strong>
                </div>
                <p>{brief.summary}</p>
                {linkedTask && (
                  <p className="brief-result">
                    task: {linkedTask.title}
                    {linkedTask.resultSummary ? ` — ${linkedTask.resultSummary}` : ""}
                  </p>
                )}
              </li>
            );
          })}
        </ol>
      ) : (
        <p className="empty brief-empty">No research/build briefs stored.</p>
      )}
    </section>
  );
}
