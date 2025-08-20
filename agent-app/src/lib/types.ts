
export interface Source {
  title: string;
  url: string;
}

export interface Message {
  type: "user" | "assistant";
  content: string;
  sources?: Source[];
}

export interface Judgment {
  strengths: string[];
  weaknesses: string[];
  improvements: string[];
  conclusion: string;
  bestAnswer?: string;
  answerText?: string; // original answer content
  sources?: { title: string; url: string }[]; // URLs for the answer
}

export interface JudgeStreamEvent{
  type:"answer1"|"answer2"|"answer3"|"judgment";
  content:string;
  source?:{title:string;url:string}[];
}

