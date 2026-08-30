import { useEffect, useState } from "react";

import ActivityStream from "./components/ActivityStream.jsx";
import ProjectOverview, { projectHealth } from "./components/ProjectOverview.jsx";
import ProjectStatus from "./components/ProjectStatus.jsx";
import TaskConsole from "./components/TaskConsole.jsx";
import { useProjectDashboard } from "./hooks/useProjectDashboard.js";

export default function App() {
  const { projects, activity, isLoading, isLive, error } = useProjectDashboard();
  const [selectedProjectId, setSelectedProjectId] = useState(null);

  useEffect(() => {
    if (!selectedProjectId && projects.length) setSelectedProjectId(projects[0].id);
  }, [projects, selectedProjectId]);

  const selectedProject = projects.find((project) => project.id === selectedProjectId);

  return (
    <main className="console">
      <header className="console-header">
        <div><p>AI PLAYGROUND // PROJECT OVERVIEW</p><h1>Your projects at a glance</h1></div>
        <p className={`connection ${isLive ? "live" : "offline"}`}>
          <span aria-hidden="true" /> {isLive ? "CONNECTED" : "RECONNECTING"}
        </p>
      </header>

      {error && <p className="system-error">! {error}</p>}
      {isLoading ? <p className="system-message">&gt; loading project state…</p> : (
        <nav className="project-tabs" aria-label="Choose a project">
          {projects.map((project) => (
            <button
              key={project.id}
              type="button"
              className={project.id === selectedProjectId ? "active" : ""}
              onClick={() => setSelectedProjectId(project.id)}
            >
              <span>{project.name}</span>
              <small>{projectHealth(project.status)}</small>
            </button>
          ))}
        </nav>
      )}

      {selectedProject && (
        <>
          <ProjectOverview project={selectedProject} isLive={isLive} />

          <details className="technical-details">
            <summary><span>&gt;</span> Technical Details</summary>
            <div className="technical-content">
              <ProjectStatus project={selectedProject} selected={false} onSelect={() => {}} />
              <TaskConsole project={selectedProject} />
              <ActivityStream events={activity} />
            </div>
          </details>
        </>
      )}

      <footer>&gt; Project information updates automatically</footer>
    </main>
  );
}
