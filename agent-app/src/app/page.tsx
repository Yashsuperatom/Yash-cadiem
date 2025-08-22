"use client";

import { useState, useRef, useEffect } from "react";
import {Message,JudgeStreamEvent} from "@/lib/types";
import { fetchJudgmentStream } from "@/lib/api";
import { marked } from 'marked';

// Define Source type if not imported
type Source = {
    title: string;
    url?: string;
};

// Simple function to convert basic markdown to HTML
const markdownToHtml = (markdown: string) => {
  // Configure marked options
  marked.setOptions({
    breaks: true, // Convert \n to <br>
    gfm: true,    // GitHub flavored markdown
  });
  
  const html = marked(markdown);
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
            answer1: "",
            answer2: "",
            answer3: "",
            judgment: "",
            sources: [],
            sources1: [],
            sources2: [],
            sources3: [],
        };

        setStreamingMessage(newStreamingMessage);

        const onEvent = (event: JudgeStreamEvent) => {
            setStreamingMessage(prev => {
                if (!prev) return null;

                const updatedMessage = { ...prev };

                switch (event.type) {
                    case "answer1_start":
                        setCurrentAgent("Global Context Agent");
                        break;
                    case "answer1":
                        updatedMessage.answer1 = (updatedMessage.answer1 || "") + event.content;
                        break;
                    case "answer1_complete":
                        updatedMessage.sources1 = event.sources || [];
                        break;
                    case "answer2_start":
                        setCurrentAgent("Base LLM Knowledge Agent");
                        break;
                    case "answer2":
                        updatedMessage.answer2 = (updatedMessage.answer2 || "") + event.content;
                        break;
                    case "answer2_complete":
                        updatedMessage.sources2 = event.sources || [];
                        break;
                    case "answer3_start":
                        setCurrentAgent("Local File Agent");
                        break;
                    case "answer3":
                        updatedMessage.answer3 = (updatedMessage.answer3 || "") + event.content;
                        break;
                    case "answer3_complete":
                        updatedMessage.sources3 = event.sources || [];
                        break;
                    case "judgment_start":
                        setCurrentAgent("Final Response");
                        break;
                    case "judgment":
                        updatedMessage.judgment = (updatedMessage.judgment || "") + event.content;
                        break;
                    case "complete":
                        // Stream completed - move streaming message to messages array
                        setMessages(prev => [...prev, updatedMessage]);
                        setIsLoading(false);
                        setCurrentAgent(null);
                        setStreamingMessage(null); // Clear streaming message
                        return null; // Return null to clear the streaming message state
                }

                return updatedMessage;
            });
        };

        try {
            const cancel = await fetchJudgmentStream(messageContent, onEvent, () => {
                // On cancel, save what we have if there's any content
                setStreamingMessage(current => {
                    if (current && (current.answer1 || current.answer2 || current.answer3 || current.judgment)) {
                        setMessages(prev => [...prev, current]);
                    }
                    setStreamingMessage(null); // Clear streaming message
                    return null;
                });
                setIsLoading(false);
                setCurrentAgent(null);
            });

            cancelStreamRef.current = cancel;

        } catch (err) {
            console.error(err);
            setError("Error: Could not fetch streaming response. Please try again.");
            
            // On error, save partial results if any
            setStreamingMessage(current => {
                if (current && (current.answer1 || current.answer2 || current.answer3 || current.judgment)) {
                    setMessages(prev => [...prev, current]);
                }
                setStreamingMessage(null); // Clear streaming message
                return null;
            });
            setIsLoading(false);
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
  
  const renderSources = (sources: Source[] | undefined) => {
    if (!sources || sources.length === 0) return null;
    
    return (
      <div className="mt-3 pt-3 border-t border-gray-200">
        <h4 className="font-semibold text-sm text-gray-600 mb-2">Sources:</h4>
        <ul className="space-y-1">
          {sources.map((source, i) => (
            <li key={i}>
              {source.url && source.url !== "#" ? (
                <a 
                  href={source.url} 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="text-blue-600 hover:text-blue-800 underline text-sm"
                >
                  {source.title}
                </a>
              ) : (
                <span className="text-gray-600 text-sm">{source.title}</span>
              )}
            </li>
          ))}
        </ul>
      </div>
    );
  };

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-4`}>
      <div className={`max-w-[80%] p-4 rounded-lg ${
        isUser 
          ? "bg-blue-500 text-white" 
          : "bg-white border border-gray-200 shadow-sm"
      }`}>
        {isUser ? (
          <div>{msg.content}</div>
        ) : (
          <div className="space-y-4">
            {/* Answer 1 */}
            {msg.answer1 && (
              <div>
                <h3 className="font-semibold text-blue-600 mb-2">Global Context Agent:</h3>
                <div 
                  className="prose prose-sm max-w-none"
                  dangerouslySetInnerHTML={markdownToHtml(msg.answer1)} 
                />
                {renderSources(msg.sources1)}
              </div>
            )}
            
            {/* Answer 2 */}
            {msg.answer2 && (
              <div>
                <h3 className="font-semibold text-green-600 mb-2">Base LLM Knowledge Agent:</h3>
                <div 
                  className="prose prose-sm max-w-none"
                  dangerouslySetInnerHTML={markdownToHtml(msg.answer2)} 
                />
                {renderSources(msg.sources2)}
              </div>
            )}
            
            {/* Answer 3 */}
            {msg.answer3 && (
              <div>
                <h3 className="font-semibold text-purple-600 mb-2">Local File Agent:</h3>
                <div 
                  className="prose prose-sm max-w-none"
                  dangerouslySetInnerHTML={markdownToHtml(msg.answer3)} 
                />
                {renderSources(msg.sources3)}
              </div>
            )}
            
            {/* Final Judgment */}
            {msg.judgment && (
              <div className="border-t border-gray-200 pt-4">
                <h3 className="font-semibold text-orange-600 mb-2">Final Response:</h3>
                <div 
                  className="prose prose-sm max-w-none"
                  dangerouslySetInnerHTML={markdownToHtml(msg.judgment)} 
                />
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