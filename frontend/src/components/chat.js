const CHAT_ENDPOINT = "http://72.60.43.188:8001/api/v1/chat";

export async function sendMessage(message) {
  const response = await fetch(CHAT_ENDPOINT, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ prompt: message }),
  });

  let data;
  try {
    data = await response.json();
  } catch {
    throw new Error("The assistant returned an invalid response.");
  }

  if (!response.ok) {
    throw new Error(data.error?.message || "Chat request failed.");
  }

  if (typeof data.response !== "string") {
    throw new Error("The assistant response was missing.");
  }

  return data.response;
}
