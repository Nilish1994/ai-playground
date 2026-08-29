import { useEffect, useMemo, useState } from "react";

import { fetchProjects, subscribeToProjectEvents } from "../services/projectApi.js";

function sortEvents(events) {
  return [...events].sort((first, second) => new Date(second.time) - new Date(first.time));
}

export function useProjectDashboard() {
  const [projects, setProjects] = useState([]);
  const [liveEvents, setLiveEvents] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isLive, setIsLive] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();

    fetchProjects(controller.signal)
      .then((data) => {
        setProjects(data);
        setError("");
      })
      .catch((requestError) => {
        if (requestError.name !== "AbortError") {
          setError(requestError.message || "Unable to load project status.");
        }
      })
      .finally(() => setIsLoading(false));

    const unsubscribe = subscribeToProjectEvents({
      onOpen: () => {
        setIsLive(true);
        setError("");
      },
      onError: () => {
        setIsLive(false);
        setError("Live event stream disconnected; reconnecting…");
      },
      onEvent: ({ project, event }) => {
        setProjects((current) => {
          const exists = current.some((item) => item.id === project.id);
          return exists
            ? current.map((item) => (item.id === project.id ? project : item))
            : [...current, project];
        });
        setLiveEvents((current) => [event, ...current.filter((item) => item.id !== event.id)]);
        setError("");
      },
    });

    return () => {
      controller.abort();
      unsubscribe();
    };
  }, []);

  const activity = useMemo(() => {
    const persistedEvents = projects.flatMap((project) => project.activity);
    const uniqueEvents = new Map(
      [...liveEvents, ...persistedEvents].map((event) => [event.id, event]),
    );
    return sortEvents([...uniqueEvents.values()]).slice(0, 100);
  }, [liveEvents, projects]);

  return { projects, activity, isLoading, isLive, error };
}
