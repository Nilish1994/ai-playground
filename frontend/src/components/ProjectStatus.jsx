import StatusBadge from "./StatusBadge.jsx";

function formatTime(value) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "medium",
  }).format(new Date(value));
}

export default function ProjectStatus({ project, selected, onSelect }) {
  return (
    <article className={`project ${selected ? "selected" : ""}`} aria-labelledby={`${project.id}-title`}>
      <header className="project-heading">
        <button className="project-select" type="button" onClick={onSelect}>
          <span className="prompt-mark">$</span>
          <h2 id={`${project.id}-title`}>{project.name}</h2>
        </button>
        <StatusBadge status={project.status} />
      </header>

      <dl className="project-details">
        <dt>path</dt><dd>{project.path}</dd>
        <dt>current_task</dt><dd>{project.currentTask}</dd>
        <dt>last_completed</dt><dd>{project.lastCompletedTask}</dd>
        <dt>updated</dt><dd>{formatTime(project.lastUpdated)}</dd>
        <dt>agent</dt><dd>{project.agent ?? "not assigned"}</dd>
      </dl>

      <section className="project-section" aria-label={`${project.name} checks`}>
        <h3>checks</h3>
        <ul className="checks">
          {project.checks.map((check) => (
            <li key={check.label}>
              <StatusBadge status={check.status} />
              <span className="check-label">{check.label}</span>
              <span className="muted">{check.detail}</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="project-section" aria-label={`${project.name} changed files`}>
        <h3>recent_files</h3>
        {project.changedFiles.length ? (
          <ul className="file-list">
            {project.changedFiles.map((file) => <li key={file}>{file}</li>)}
          </ul>
        ) : <p className="empty">no recent file data</p>}
      </section>
    </article>
  );
}
