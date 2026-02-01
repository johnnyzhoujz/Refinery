import { useState, useEffect } from "react";
import { api } from "../api";
import type { AnalysisResult, Hypothesis, ProgressEvent } from "../api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Loader2, CheckCircle2, AlertTriangle, Zap, Save } from "lucide-react";

export default function Home() {
  const [traceId, setTraceId] = useState("");
  const [expectedBehavior, setExpectedBehavior] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [progress, setProgress] = useState<string[]>([]);
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);
  const [hypotheses, setHypotheses] = useState<Hypothesis[]>([]);
  const [activeTab, setActiveTab] = useState("analysis");
  const [savedVersion, setSavedVersion] = useState<string | null>(null);

  useEffect(() => {
    // Subscribe to progress events
    const unsubscribe = api.subscribeToProgress((event: ProgressEvent) => {
      if (event.event === "analysis_started") {
        setProgress(prev => [...prev, `Started analysis for ${event.payload.trace_id}`]);
      } else if (event.event === "analysis_completed") {
        setProgress(prev => [...prev, "Analysis complete!"]);
      } else {
        // Generic progress
        if (event.payload && typeof event.payload === 'string') {
           setProgress(prev => [...prev, event.payload]);
        }
      }
    });
    return () => unsubscribe();
  }, []);

  const handleAnalyze = async () => {
    if (!traceId || !expectedBehavior) return;
    setIsLoading(true);
    setAnalysis(null);
    setHypotheses([]);
    setProgress([]);
    setSavedVersion(null);

    try {
      const result = await api.analyze(traceId, expectedBehavior);
      setAnalysis(result);
      setActiveTab("analysis");
      
      // Auto-generate hypotheses
      setProgress(prev => [...prev, "Generating hypotheses..."]);
      const hypos = await api.generateHypotheses(traceId, result.diagnosis);
      setHypotheses(hypos);
      setProgress(prev => [...prev, "Hypotheses generated!"]);
      
    } catch (err) {
      console.error(err);
      setProgress(prev => [...prev, "Error occurred during analysis."]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSave = async (hypothesis: Hypothesis) => {
    try {
      const res = await api.saveExperiment(hypothesis);
      setSavedVersion(res.version_id);
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="container mx-auto p-8 max-w-5xl space-y-8">
      <div className="text-center space-y-4">
        <h1 className="text-4xl font-bold tracking-tight">Refinery</h1>
        <p className="text-muted-foreground text-lg">AI-powered trace analysis and self-healing.</p>
      </div>

      {/* Input Section */}
      <Card>
        <CardHeader>
          <CardTitle>New Analysis</CardTitle>
          <CardDescription>Enter a trace ID and what you expected to happen.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-4 gap-4">
            <div className="col-span-1">
              <Input 
                placeholder="Trace ID" 
                value={traceId} 
                onChange={e => setTraceId(e.target.value)} 
              />
            </div>
            <div className="col-span-3">
              <Input 
                placeholder="Expected Behavior (e.g., 'The agent should verify the user ID before refunding')" 
                value={expectedBehavior} 
                onChange={e => setExpectedBehavior(e.target.value)} 
                onKeyDown={e => e.key === 'Enter' && handleAnalyze()}
              />
            </div>
          </div>
        </CardContent>
        <CardFooter className="flex justify-between">
          <div className="text-sm text-muted-foreground">
            {isLoading && (
              <span className="flex items-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin" />
                {progress[progress.length - 1] || "Processing..."}
              </span>
            )}
          </div>
          <Button onClick={handleAnalyze} disabled={isLoading || !traceId || !expectedBehavior}>
            {isLoading ? "Analyzing..." : "Run Analysis"}
          </Button>
        </CardFooter>
      </Card>

      {/* Results Section */}
      {analysis && (
        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="analysis">Diagnosis</TabsTrigger>
            <TabsTrigger value="hypotheses">Hypotheses & Fixes</TabsTrigger>
          </TabsList>
          
          <TabsContent value="analysis" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <AlertTriangle className="h-5 w-5 text-yellow-500" />
                  Diagnosis: {analysis.diagnosis.failure_type}
                </CardTitle>
                <CardDescription>Severity: <Badge variant="secondary">{analysis.diagnosis.severity || "High"}</Badge></CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="p-4 bg-muted rounded-md">
                  <h4 className="font-semibold mb-2">Root Cause</h4>
                  <p className="text-sm">{analysis.diagnosis.root_cause}</p>
                </div>
                
                {/* Gap Analysis Visualization would go here */}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="hypotheses" className="space-y-4">
            {hypotheses.map(hyp => (
              <Card key={hyp.id}>
                <CardHeader>
                  <CardTitle className="flex justify-between items-center">
                    <span className="flex items-center gap-2">
                      <Zap className="h-5 w-5 text-blue-500" />
                      {hyp.description}
                    </span>
                    <Badge>{hyp.confidence} Confidence</Badge>
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <p className="text-sm text-muted-foreground">{hyp.rationale}</p>
                  
                  {hyp.proposed_changes.map((change, idx) => (
                    <div key={idx} className="border rounded-md overflow-hidden">
                      <div className="bg-muted px-4 py-2 text-xs font-mono border-b flex justify-between">
                        <span>{change.file_path}</span>
                        <span className="uppercase">{change.change_type}</span>
                      </div>
                      <div className="grid grid-cols-2 text-xs font-mono">
                         <div className="p-4 bg-red-50/50 dark:bg-red-950/20 overflow-x-auto whitespace-pre-wrap border-r">
                           {change.original_content}
                         </div>
                         <div className="p-4 bg-green-50/50 dark:bg-green-950/20 overflow-x-auto whitespace-pre-wrap">
                           {change.new_content}
                         </div>
                      </div>
                    </div>
                  ))}
                </CardContent>
                <CardFooter>
                  <Button 
                    className="w-full gap-2" 
                    onClick={() => handleSave(hyp)}
                    disabled={!!savedVersion}
                  >
                    {savedVersion ? <CheckCircle2 className="h-4 w-4" /> : <Save className="h-4 w-4" />}
                    {savedVersion ? `Saved Version ${savedVersion}` : "Save Experiment Version"}
                  </Button>
                </CardFooter>
              </Card>
            ))}
            
            {hypotheses.length === 0 && !isLoading && (
               <div className="text-center p-8 text-muted-foreground">No hypotheses generated.</div>
            )}
          </TabsContent>
        </Tabs>
      )}
    </div>
  );
}
