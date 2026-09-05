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
  const memory = project.memory;
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
        <p>{memory?.purpose || latestBrief?.summary || "No project purpose has been recorded yet."}</p>
      </section>

      <section className="overview-section project-memory">
        <h3>PROJECT MEMORY</h3>
        <dl>
          <dt>Purpose</dt><dd>{memory?.purpose || "Not recorded yet."}</dd>
          <dt>Current state</dt><dd>{memory?.currentState || "Not recorded yet."}</dd>
          <dt>Current focus</dt><dd>{memory?.currentFocus || "No focus recorded."}</dd>
          <dt>Next steps</dt>
          <dd>
            {memory?.nextSteps?.length
              ? memory.nextSteps.join(" · ")
              : "No next steps recorded."}
          </dd>
        </dl>
        {memory && (memory.architectureSummary || memory.importantDecisions.length || memory.codingRules.length) && (
          <details className="memory-details">
            <summary><span aria-hidden="true">›</span> More project context</summary>
            {memory.architectureSummary && <p><strong>Architecture:</strong> {memory.architectureSummary}</p>}
            {memory.importantDecisions.length > 0 && <p><strong>Decisions:</strong> {memory.importantDecisions.join(" · ")}</p>}
            {memory.codingRules.length > 0 && <p><strong>Coding rules:</strong> {memory.codingRules.join(" · ")}</p>}
          </details>
        )}
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
    </article>
  );
}
