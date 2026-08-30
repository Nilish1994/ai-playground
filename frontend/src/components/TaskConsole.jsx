import { useEffect, useMemo, useState } from "react";

import StatusBadge from "./StatusBadge.jsx";

const EVENT_LABELS = {
  task_created: "TASK",
  prompt_generated: "TASK",
  task_started: "TASK",
  task_completed: "DONE",
  task_failed: "FAIL",
  agent_started: "CODEX",
  agent_thinking: "CODEX",
  agent_finished: "CODEX",
  command_started: "CMD",
  command_completed: "CMD",
  file_created: "FILE",
  file_changed: "FILE",
  file_deleted: "FILE",
  test_started: "TEST",
  test_passed: "PASS",
  test_failed: "FAIL",
  build_started: "BUILD",
  build_passed: "PASS",
  build_failed: "FAIL",
};

function time(value) {
  return new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(new Date(value));
}

export default function TaskConsole({ project }) {
  const [selectedTaskId, setSelectedTaskId] = useState(null);
  const activeTask = project.tasks.find((task) => task.status === "RUNNING") || project.tasks[0];

  useEffect(() => {
    setSelectedTaskId((current) => {
      if (project.tasks.some((task) => task.id === current)) return current;
      return activeTask?.id ?? null;
    });
  }, [activeTask?.id, project.id, project.tasks]);

  const selectedTask = project.tasks.find((task) => task.id === selectedTaskId) || activeTask;
  const events = useMemo(
    () => project.activity
      .filter((event) => event.taskId === selectedTask?.id)
      .sort((first, second) => new Date(first.time) - new Date(second.time)),
    [project.activity, selectedTask?.id],
  );

  return (
    <section className="task-console" aria-labelledby="task-console-title">
      <header className="section-heading">
        <h2 id="task-console-title">{project.name} // Recent Work</h2>
        <span>{project.tasks.length} tasks</span>
      </header>

      <div className="task-layout">
        <ol className="task-history">
          {project.tasks.map((task) => (
            <li key={task.id}>
              <button
                type="button"
                className={task.id === selectedTask?.id ? "active" : ""}
                onClick={() => setSelectedTaskId(task.id)}
              >
                <StatusBadge status={task.status} />
                <span>{task.title}</span>
                <time>{time(task.updatedAt)}</time>
              </button>
            </li>
          ))}
          {!project.tasks.length && <li className="empty">no task history</li>}
        </ol>

        <div className="task-timeline">
          <div className="task-context">
            <span>task: {selectedTask?.title ?? "none"}</span>
            <span>agent: {selectedTask?.agent ?? "not assigned"}</span>
          </div>
          <h3>Technical Activity</h3>
          <ol>
            {events.map((event) => (
              <li key={event.id}>
                <time>{time(event.time)}</time>
                <span className={`timeline-label label-${EVENT_LABELS[event.type]?.toLowerCase()}`}>
                  [{EVENT_LABELS[event.type] || "EVENT"}]
                </span>
                <span>{event.message}</span>
                {event.file && <code>{event.file}</code>}
              </li>
            ))}
            {selectedTask && !events.length && <li className="empty">no events recorded</li>}
          </ol>
        </div>
      </div>
    </section>
  );
}
