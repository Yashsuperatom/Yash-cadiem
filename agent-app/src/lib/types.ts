
export interface Source {
  title: string;
  url: string;
}
// --- Types for streaming API ---
export interface JudgeStreamEvent {
  type: "answer1" | "answer2" | "answer3" | "judgment" | 
        "answer1_start" | "answer2_start" | "answer3_start" | "judgment_start" |
        "answer1_complete" | "answer2_complete" | "answer3_complete" | "complete";
  content: string;
  sources?: { title: string; url: string }[];
}


export interface Message {

    sources?: any;
    source_used?:string;
    explanation?:string;
     id: string;
  type: "user" | "assistant";
  content: string;
  answer1?: string;
  answer2?: string;
  answer3?: string;
  judgment?: string;
  sources1?: Source[];
  sources2?: Source[];
  sources3?: Source[];
  suggestions?: string;
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


