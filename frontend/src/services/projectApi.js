const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://72.60.43.188:8001/api/v1";

function normalizeTask(task) {
  return {
    id: task.id,
    projectId: task.project_id,
    title: task.title,
    description: task.description,
    prompt: task.prompt,
    status: task.status,
    agent: task.agent,
    resultSummary: task.result_summary,
    createdAt: task.created_at,
    startedAt: task.started_at,
    completedAt: task.completed_at,
    updatedAt: task.updated_at,
  };
}

function normalizeBrief(brief) {
  return {
    id: brief.id,
    projectId: brief.project_id,
    title: brief.title,
    summary: brief.summary,
    decisions: brief.decisions,
    buildPrompt: brief.build_prompt,
    status: brief.status,
    taskId: brief.task_id,
    createdAt: brief.created_at,
    updatedAt: brief.updated_at,
  };
}

function normalizeEvent(event, project) {
  return {
    id: event.event_id,
    projectId: project.id,
    projectName: project.name,
    taskId: event.task_id,
    time: event.timestamp,
    status: event.status,
    type: event.type,
    message: event.message,
    agent: event.agent,
    file: event.file,
    metadata: event.metadata,
  };
}

export function normalizeProject(project) {
  return {
    id: project.id,
    name: project.name,
    path: project.path,
    status: project.status,
    currentTask: project.current_task || "No active task",
    lastCompletedTask: project.last_completed_task || "No completed task recorded",
    lastUpdated: project.updated_at,
    agent: project.active_agent,
    changedFiles: project.recent_files,
    checks: project.checks,
    tasks: project.tasks.map(normalizeTask),
    briefs: (project.briefs || []).map(normalizeBrief),
    activity: project.recent_events.map((event) => normalizeEvent(event, project)),
  };
}

export async function fetchProjects(signal) {
  const response = await fetch(`${API_BASE_URL}/projects`, { signal });
  if (!response.ok) throw new Error(`Project status request failed (${response.status}).`);
  return (await response.json()).map(normalizeProject);
}

export function subscribeToProjectEvents({ onEvent, onOpen, onError }) {
  const source = new EventSource(`${API_BASE_URL}/events/stream`);
  source.addEventListener("open", onOpen);
  source.addEventListener("error", onError);
  source.addEventListener("project_event", (message) => {
    const payload = JSON.parse(message.data);
    const project = normalizeProject(payload.project);
    onEvent({ project, event: normalizeEvent(payload.event, payload.project) });
  });
  return () => source.close();
}
