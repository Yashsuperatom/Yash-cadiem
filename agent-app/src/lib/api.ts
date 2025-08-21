import { JudgeStreamEvent } from "@/lib/types";



export async function fetchJudgmentStream(
    message: string,
    onEvent: (event: JudgeStreamEvent) => void,
    onCancel: () => void
): Promise<() => void> {
    const controller = new AbortController();
    const signal = controller.signal;

    try {
        const response = await fetch("http://127.0.0.1:8002/app/judge/stream", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message }),
            signal,
        });

        if (!response.body) {
            throw new Error("ReadableStream not supported or no response body");
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let buffer = "";

        // Cancel function to expose to the parent component
        const cancel = () => {
            reader.cancel("User cancelled the request.");
            onCancel();
        };

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });

            const parts = buffer.split("\n\n");

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

            buffer = parts[parts.length - 1];
        }
        return () => {}; // Return a no-op function if the stream completes normally
    } catch (err) {
        // Corrected type checking for the error object
        if (err instanceof Error && err.name === 'AbortError') {
            console.log("Fetch aborted by user.");
            onCancel();
            return () => {};
        }
        console.error("Failed to fetch judgment stream:", err);
        throw err;
    }
}

