import { useState } from "react";

import { sendMessage } from "./chat.js";

const initialMessages = [
  { id: "welcome", role: "assistant", text: "Hello. What can I help you with?" },
];

export default function Chat() {
  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState(initialMessages);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(event) {
    event.preventDefault();
    const prompt = message.trim();
    if (!prompt || isLoading) return;

    setMessages((current) => [
      ...current,
      { id: crypto.randomUUID(), role: "user", text: prompt },
    ]);
    setMessage("");
    setError("");
    setIsLoading(true);

    try {
      const reply = await sendMessage(prompt);
      setMessages((current) => [
        ...current,
        { id: crypto.randomUUID(), role: "assistant", text: reply },
      ]);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Chat request failed.");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <section className="chat" aria-label="Chat with AI Playground">
      <div className="messages" aria-live="polite">
        {messages.map((item) => (
          <p key={item.id} className={`message ${item.role}`}>
            {item.text}
          </p>
        ))}
        {isLoading && <p className="message assistant loading">Thinking…</p>}
      </div>

      <form className="composer" onSubmit={handleSubmit}>
        <label className="sr-only" htmlFor="message">
          Message
        </label>
        <textarea
          id="message"
          rows="2"
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          placeholder="Ask anything…"
          disabled={isLoading}
        />
        <button type="submit" disabled={isLoading || !message.trim()}>
          {isLoading ? "Sending…" : "Send"}
        </button>
      </form>

      <p className="error" role="alert">
        {error}
      </p>
    </section>
  );
}
