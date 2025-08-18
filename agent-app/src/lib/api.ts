// lib/api.ts

export interface JudgeStreamEvent {
  type: "answer1" | "answer2" | "answer3" | "judgment";
  content: string;
  sources?: { title: string; url: string }[]; // Included only with "judgment" or "answer1"/"answer3" if applicable
}

/**
 * Fetch streaming response from /app/judge/stream using POST and ReadableStream.
 * Calls onEvent for each new chunk of data.
 */
export async function fetchJudgmentStream(
  message: string,
  onEvent: (event: JudgeStreamEvent) => void
): Promise<void> {
  const response = await fetch("http://127.0.0.1:8000/app/judge/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });

  if (!response.body) {
    throw new Error("ReadableStream not supported or no response body");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    // SSE sends events separated by double newlines: \n\n
    const parts = buffer.split("\n\n");

    // Process all complete events except possibly last incomplete one
    for (let i = 0; i < parts.length - 1; i++) {
      const eventStr = parts[i];
      if (eventStr.startsWith("data: ")) {
        const jsonStr = eventStr.slice(6).trim();
        try {
          const eventObj: JudgeStreamEvent = JSON.parse(jsonStr);
          onEvent(eventObj);
        } catch (e) {
          console.error("Failed to parse SSE JSON:", e);
        }
      }
    }

    // Keep the incomplete part for next chunk
    buffer = parts[parts.length - 1];
  }
}
