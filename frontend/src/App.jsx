import { useEffect, useState } from "react";

import ActivityStream from "./components/ActivityStream.jsx";
import BriefsPanel from "./components/BriefsPanel.jsx";
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
        <div><p>AI PLAYGROUND // PROJECT OPERATIONS</p><h1>project_status</h1></div>
        <p className={`connection ${isLive ? "live" : "offline"}`}>
          <span aria-hidden="true" /> {isLive ? "LIVE" : "CONNECTING"}
        </p>
      </header>

      <section className="summary" aria-label="Project summary">
        <span>projects: {projects.length}</span>
        <span>running: {projects.filter((project) => project.status === "RUNNING").length}</span>
        <span>failed: {projects.filter((project) => project.status === "FAILED").length}</span>
        <span>source: postgres+sse</span>
      </section>

      {error && <p className="system-error">! {error}</p>}
      {isLoading ? <p className="system-message">&gt; loading project state…</p> : (
        <section className="project-grid" aria-label="Projects">
          {projects.map((project) => (
            <ProjectStatus
              key={project.id}
              project={project}
              selected={project.id === selectedProjectId}
              onSelect={() => setSelectedProjectId(project.id)}
            />
          ))}
        </section>
      )}

      {selectedProject && <BriefsPanel project={selectedProject} />}
      {selectedProject && <TaskConsole project={selectedProject} />}
      <ActivityStream events={activity} />
      <footer>&gt; dashboard ready — listening for project and task events</footer>
    </main>
  );
}
