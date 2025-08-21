
export interface Source {
    title: string;
    url: string;
}

export interface Message {
    id: string;
    type: "user" | "assistant";
    content: string;
    judgment?: string;
    sources?: Source[];
    source_used?:string;
    suggestions ?:string;
    explanation?:string;
  }
  
  export interface Judgment {
  // Core evaluation
  strengths: string[];          // Positive points about the answer
  weaknesses: string[];         // Negative points
  improvements: string[];       // Suggested improvements
  conclusion: string;           // Final conclusion or verdict

  // Answer-related
  bestAnswer?: string;          // Best refined answer chosen by agent
  answerText?: string;          // Original answer content (raw)
  selectedAnswer?: string;      // If multiple answers, which one is picked

  // Metadata
  sources?: {                   // Reference sources used in the judgment
    title: string;
    url: string;
  }[];

  // Optional future extensions
  explanation?: string;         // Why this answer was chosen
  confidenceScore?: number;     // 0–1 score for confidence
  evaluatedAt?: string;         // ISO timestamp of evaluation
  evaluator?: string;           // Which agent / model evaluated
}


// --- Types for streaming API ---
export interface JudgeStreamEvent {
    type: "answer1" | "answer2" | "answer3" | "judgment";
    content: string;
    sources?: { title: string; url: string }[];
}
