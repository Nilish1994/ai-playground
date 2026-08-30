const HEALTH_LABELS = {
  DONE: "HEALTHY",
  RUNNING: "WORKING",
  FAILED: "ATTENTION",
  IDLE: "IDLE",
};

function newest(items, status) {
  return items
    .filter((item) => item.status === status)
    .sort((first, second) => new Date(second.updatedAt) - new Date(first.updatedAt));
}

export function projectHealth(status) {
  return HEALTH_LABELS[status] || "IDLE";
}

export default function ProjectOverview({ project, isLive }) {
  const currentTask = project.tasks.find((task) => task.status === "RUNNING");
  const plannedTasks = newest(project.tasks, "PENDING");
  const completedTasks = newest(project.tasks, "DONE").slice(0, 10);
  const latestBrief = project.briefs[0];
  const decisions = [...new Set(project.briefs.flatMap((brief) => brief.decisions))].slice(0, 5);
  const currentResult = currentTask?.resultSummary
    || (currentTask ? "Work is underway. Updates will appear here automatically." : null);

  return (
    <article className="human-overview">
      <header className="overview-title">
        <div><span className="prompt-mark">$</span><h2>{project.name}</h2></div>
        <span className={`health health-${projectHealth(project.status).toLowerCase()}`}>
          <i aria-hidden="true" /> {projectHealth(project.status)}
        </span>
      </header>

      <section className="overview-section">
        <h3>WHAT ARE WE BUILDING?</h3>
        <p>{latestBrief?.summary || "No project purpose has been recorded yet."}</p>
      </section>

      <section className="overview-section current-work">
        <h3>CURRENT WORK</h3>
        <p className="work-title">{currentTask?.title || "No work is currently active."}</p>
        {currentTask && (
          <dl>
            <dt>Status</dt><dd>In progress</dd>
            <dt>Agent</dt><dd>{currentTask.agent || "No agent assigned"}</dd>
            <dt>Progress</dt><dd>{currentResult}</dd>
          </dl>
        )}
      </section>

      <div className="overview-columns">
        <section className="overview-section">
          <h3>WHAT WE HAVE COMPLETED</h3>
          {completedTasks.length ? (
            <ul className="human-list completed-list">
              {completedTasks.map((task) => (
                <li key={task.id}>
                  <strong>{task.title}</strong>
                  {task.resultSummary && <span>{task.resultSummary}</span>}
                </li>
              ))}
            </ul>
          ) : (
            <p className="human-empty">No completed work recorded yet.</p>
          )}
        </section>

        <section className="overview-section">
          <h3>WHAT&apos;S NEXT</h3>
          {plannedTasks.length ? (
            <ul className="human-list next-list">
              {plannedTasks.slice(0, 5).map((task) => <li key={task.id}>{task.title}</li>)}
            </ul>
          ) : (
            <p className="human-empty">No next milestone has been recorded.</p>
          )}
        </section>
      </div>

      <section className="overview-section">
        <h3>RECENT DECISIONS</h3>
        {decisions.length ? (
          <ul className="human-list decision-list">
            {decisions.map((decision) => <li key={decision}>{decision}</li>)}
          </ul>
        ) : (
          <p className="human-empty">No recent decisions have been recorded.</p>
        )}
      </section>

      <section className="overview-section system-overview">
        <h3>SYSTEM STATUS</h3>
        <dl>
          <dt>API</dt><dd>Healthy</dd>
          <dt>Database</dt><dd>Healthy</dd>
          <dt>Live connection</dt><dd>{isLive ? "Connected" : "Reconnecting"}</dd>
        </dl>
      </section>
    </article>
  );
}
