// API Client for Refinery Server

const API_BASE = import.meta.env.DEV ? "http://localhost:8000" : "";

export interface Trace {
  trace_id: string;
  project_name: string;
  runs: any[];
  metadata: any;
}

export interface AnalysisResult {
  trace_analysis: any;
  gap_analysis: any;
  diagnosis: {
    failure_type: string;
    root_cause: string;
    severity: string;
    [key: string]: any;
  };
}

export interface Hypothesis {
  id: string;
  description: string;
  rationale: string;
  confidence: string;
  proposed_changes: ProposedChange[];
  example_before?: string;
  example_after?: string;
}

export interface ProposedChange {
  file_path: string;
  original_content: string;
  new_content: string;
  change_type: string;
  description: string;
}

export interface ProgressEvent {
  event: string;
  payload: any;
  timestamp: number;
}

export const api = {
  checkHealth: async () => {
    const res = await fetch(`${API_BASE}/api/health`);
    return res.json();
  },

  getTrace: async (traceId: string) => {
    const res = await fetch(`${API_BASE}/api/trace/${traceId}`);
    if (!res.ok) throw new Error("Failed to fetch trace");
    return res.json();
  },

  analyze: async (traceId: string, expectedBehavior: string) => {
    const res = await fetch(`${API_BASE}/api/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ trace_id: traceId, expected_behavior: expectedBehavior }),
    });
    if (!res.ok) throw new Error("Analysis failed");
    return res.json();
  },

  generateHypotheses: async (traceId: string, diagnosis: any) => {
    const res = await fetch(`${API_BASE}/api/hypothesize`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ trace_id: traceId, diagnosis }),
    });
    if (!res.ok) throw new Error("Hypothesis generation failed");
    return res.json();
  },
  
  saveExperiment: async (hypothesis: any) => {
    const res = await fetch(`${API_BASE}/api/experiments`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ hypothesis }),
    });
    if (!res.ok) throw new Error("Failed to save experiment");
    return res.json();
  },

  subscribeToProgress: (onMessage: (event: ProgressEvent) => void) => {
    const eventSource = new EventSource(`${API_BASE}/api/progress`);
    eventSource.onmessage = (event) => {
      try {
        const parsed = JSON.parse(event.data);
        onMessage(parsed);
      } catch (e) {
        console.error("Failed to parse progress event", e);
      }
    };
    return () => eventSource.close();
  }
};
