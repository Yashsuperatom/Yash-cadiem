"use client";

import { useState, useRef, useEffect } from "react";
import {Message,JudgeStreamEvent} from "@/lib/types";
import { fetchJudgmentStream } from "@/lib/api";


/**
 * A cancellable fetch function for streaming responses.
 * It returns a cancel function to be called by the parent component.
 */

// Simple function to convert basic markdown to HTML
const markdownToHtml = (markdown: string) => {
    // Replace bold text (e.g., **text**)
    let html = markdown.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    // Replace italic text (e.g., *text*)
    html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');
    // Replace links (e.g., [text](url))
    html = html.replace(/\[(.*?)\]\((.*?)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer" class="underline text-blue-600 hover:text-blue-400 transition-colors duration-200">$1</a>');
    // Replace newline characters with <br> for line breaks
    html = html.replace(/\n/g, '<br />');

    return { __html: html };
};

// --- Custom Hook for Chat Logic ---
function useChat() {
    const [input, setInput] = useState("");
    const [messages, setMessages] = useState<Message[]>([
        {
            id: '0',
            type: 'assistant',
            content: ''
        }
    ]);
    const [streamingMessage, setStreamingMessage] = useState<Message | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [currentAgent, setCurrentAgent] = useState<string | null>(null);
    const messageIdRef = useRef(1);
    const cancelStreamRef = useRef<(() => void) | null>(null);

    const generateId = () => {
        messageIdRef.current += 1;
        return messageIdRef.current.toString();
    };

    const handleStop = () => {
        if (cancelStreamRef.current) {
            cancelStreamRef.current();
            // Manually update the state to reflect the stopped stream
            setIsLoading(false);
            setStreamingMessage(null);
            setCurrentAgent(null);
        }
    };

    const handleSubmit = async (messageContent: string) => {
        if (!messageContent.trim() || isLoading) return;

        const userMessage: Message = {
            id: generateId(),
            type: "user",
            content: messageContent,
        };

        setMessages((prev) => [...prev, userMessage]);
        setInput("");
        setIsLoading(true);
        setError(null);
        setCurrentAgent(null);

        const newStreamingMessage: Message = {
            id: generateId(),
            type: "assistant",
            content: "",
            sources: [],
            judgment: "",
        };
        setStreamingMessage(newStreamingMessage);

        const messageBuilder = { ...newStreamingMessage };

        const onEvent = (event: JudgeStreamEvent) => {
            // Update the agent based on the incoming event type
            if (event.type === "answer1") setCurrentAgent("Global Contex Agent");
            else if (event.type === "answer2") setCurrentAgent("Base LLM Knowledge Agent");
            else if (event.type === "answer3") setCurrentAgent("Local File Agent");
            else if (event.type === "judgment") setCurrentAgent("Main Agent");

            setStreamingMessage(prev => {
                if (!prev) return null;
                const updatedMessage = { ...prev };
                if (event.type === "answer1" || event.type === "answer2" || event.type === "answer3") {
                    updatedMessage.content += event.content;
                    messageBuilder.content = updatedMessage.content;
                    if (event.sources) {
                        updatedMessage.sources = [...(updatedMessage.sources || []), ...event.sources];
                        messageBuilder.sources = updatedMessage.sources;
                    }
                } else if (event.type === "judgment") {
                    updatedMessage.judgment += event.content;
                    messageBuilder.judgment = updatedMessage.judgment;
                    if (event.sources) {
                        updatedMessage.sources = [...(updatedMessage.sources || []), ...event.sources];
                        messageBuilder.sources = updatedMessage.sources;
                    }
                }
                return updatedMessage;
            });
        };

        try {
            const cancel = await fetchJudgmentStream(messageContent, onEvent, () => {
                setIsLoading(false);
                setStreamingMessage(null);
                setCurrentAgent(null);
            });
            cancelStreamRef.current = cancel;

            // --- ADDED MOCK JUDGMENT HERE ---
            // messageBuilder.judgment = "This is a mock judgment to show the feature works. The answer could be improved by adding more details about the streaming protocol.";
            // The stream has ended successfully, add the full message
            setMessages(prev => [...prev, messageBuilder]);
        } catch (err) {
            console.error(err);
            setError("Error: Could not fetch streaming response. Please try again.");
        } finally {
            setIsLoading(false);
            setStreamingMessage(null);
            setCurrentAgent(null);
        }
    };

    return {
        input,
        setInput,
        messages,
        streamingMessage,
        isLoading,
        error,
        currentAgent,
        handleSubmit,
        handleStop
    };
}

// --- MessageBubble Component for cleaner rendering ---
const MessageBubble = ({ msg }: { msg: Message }) => {
    const isUser = msg.type === "user";
    return (
        <div
            className={`w-full flex ${isUser ? 'justify-end' : 'justify-start'} animate-fadeIn`}
        >
            <div
                className={`max-w-3xl p-4 rounded-xl shadow-md break-words transition-transform duration-300 ease-in-out transform ${isUser
                        ? "bg-blue-600 text-white"
                        : "bg-gray-200 text-gray-800"
                    }`}
            >
                {isUser ? (
                    <div>{msg.content}</div>
                ) : (
                    <div className="flex flex-col gap-3">
                        {/* Main answer */}
                        {msg.content && (
                            <div className="whitespace-pre-wrap">
                                <span dangerouslySetInnerHTML={markdownToHtml(msg.content)} />
                            </div>
                        )}
                        {/* Judgment/improvements */}
                        {msg.judgment && (
                            <div className="bg-gray-100 p-3 rounded-lg border-l-4 border-yellow-500">
                                <strong className="text-yellow-600">Final Response</strong>
                                <p className="mt-1 whitespace-pre-wrap">{msg.judgment}</p>
                            </div>
                        )}
                        {/* Sources */}
                        {msg.sources && msg.sources.length > 0 && (
                            <div className="text-sm">
                                <strong className="text-gray-600">Sources:</strong>
                                <ul className="list-disc list-inside mt-1">
                                    {msg.sources.map((s, i) => (
                                        <li key={i}>
                                            <a
                                                href={s.url}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                className="underline text-blue-600 hover:text-blue-400 transition-colors duration-200"
                                            >
                                                {s.title}
                                            </a>
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
};

// --- Header Component ---
const Header = () => (
    <div className="w-full h-16 bg-white flex items-center justify-between p-4 shadow-lg sticky top-0 z-10">
        <h1 className="text-2xl font-bold text-gray-800">Cognify Agent</h1>
        <div className="flex items-center gap-2">
            <button className="p-2 rounded-full text-gray-800 hover:bg-gray-200 transition-colors duration-200">
                <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M12 16a2 2 0 0 0 2-2v-2a2 2 0 0 0-2-2a2 2 0 0 0-2 2v2a2 2 0 0 0 2 2z" />
                    <path d="M17 12a5 5 0 0 0-5-5h-2a5 5 0 0 0-5 5v2a5 5 0 0 0 5 5h2a5 5 0 0 0 5-5z" />
                    <path d="M12 2V5" />
                    <path d="M12 19V22" />
                </svg>
            </button>
        </div>
    </div>
);

// --- Sidebar Component ---
const Sidebar = () => (
    <div className="hidden md:flex flex-col w-64 bg-gray-200 p-4 border-r border-gray-300">
        <button className="flex items-center gap-2 p-2 rounded-xl text-gray-800 border border-gray-400 hover:bg-gray-300 transition-colors duration-200">
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 5v14M5 12h14" /></svg>
            New Chat
        </button>
        <div className="flex-1 overflow-y-auto mt-4 space-y-2">
            <div className="p-2 rounded-lg hover:bg-gray-300 transition-colors duration-200 cursor-pointer text-gray-800">
                Example Chat 1
            </div>
            <div className="p-2 rounded-lg hover:bg-gray-300 transition-colors duration-200 cursor-pointer text-gray-800">
                Example Chat 2
            </div>
        </div>
    </div>
);

// --- Main Chat Component ---
export default function Chat() {
    const { input, setInput, messages, streamingMessage, isLoading, error, currentAgent, handleSubmit, handleStop } = useChat();
    const chatEndRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages, streamingMessage, isLoading]);

    const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            handleSubmit(input);
        }
    };

    return (
        <div className="flex h-screen bg-gray-100 text-gray-800 font-sans">
            <style>
                {`
                @keyframes fadeIn {
                    from { opacity: 0; transform: translateY(10px); }
                    to { opacity: 1; transform: translateY(0); }
                }
                .animate-fadeIn {
                    animation: fadeIn 0.5s ease-out;
                }
                
                @keyframes typing {
                    from { width: 0; }
                    to { width: 100%; }
                }
                .typing-dots::after {
                    content: '...';
                    animation: typing 1.5s steps(3, end) infinite;
                }
                `}
            </style>

            <Sidebar />

            <div className="flex-1 flex flex-col">
                <Header />
                <div className="flex-1 overflow-y-auto flex flex-col gap-4 p-4 max-w-4xl mx-auto w-full">
                    {messages.map((msg) => (
                        <MessageBubble key={msg.id} msg={msg} />
                    ))}
                    {streamingMessage && <MessageBubble key={streamingMessage.id} msg={streamingMessage} />}

                    {/* Loading and Error Indicators */}
                    {isLoading && (
                        <div className="self-start bg-gray-200 text-gray-600 p-4 rounded-xl shadow-md max-w-3xl animate-fadeIn flex flex-col items-start">
                            <span className="typing-dots">Thinking</span>
                            {currentAgent && <span className="mt-2 text-sm text-gray-500">Current Agent: {currentAgent}</span>}
                            <button
                                onClick={handleStop}
                                className="mt-2 text-sm text-red-600 hover:text-red-800 transition-colors duration-200"
                            >
                                Stop
                            </button>
                        </div>
                    )}
                    {error && (
                        <div className="self-start bg-red-200 text-red-800 p-4 rounded-xl shadow-md max-w-3xl animate-fadeIn">
                            {error}
                        </div>
                    )}
                    <div ref={chatEndRef} />
                </div>

                <div className="relative p-4 bg-gray-100">
                    <div className="flex items-center gap-3 w-full max-w-4xl mx-auto p-3 bg-gray-200 rounded-xl shadow-lg">
                        <textarea
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            onKeyDown={handleKeyDown}
                            placeholder="Send a message..."
                            className="flex-1 bg-transparent border-none focus:outline-none resize-none overflow-hidden h-12 py-3 text-gray-800"
                            rows={1}
                            disabled={isLoading}
                        />
                        <button
                            onClick={() => handleSubmit(input)}
                            disabled={!input.trim() || isLoading}
                            className="p-2 rounded-full bg-blue-500 text-white disabled:opacity-50 disabled:cursor-not-allowed hover:bg-blue-600 transition-colors duration-200"
                        >
                            <svg
                                xmlns="http://www.w3.org/2000/svg"
                                width="24"
                                height="24"
                                viewBox="0 0 24 24"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="2"
                                strokeLinecap="round"
                                strokeLinejoin="round"
                            >
                                <path d="m22 2-7 19-3-8-2-2-8-3 19-7z" />
                            </svg>
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}
