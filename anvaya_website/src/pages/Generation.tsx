import { useState, useEffect, useRef } from "react";
import { motion } from "framer-motion";
import { useNavigate, useLocation } from "react-router-dom";
import { Search, Brain, Film, Check, AlertCircle } from "lucide-react";
import FloatingParticles from "@/components/FloatingParticles";
import { Progress } from "@/components/ui/progress";
import { pollStatus, type JobStatus } from "@/services/api";

const STEPS = [
  { icon: Search, label: "Extracting Concepts", description: "Parsing your manuscript for key ideas…", statusKey: "extracting" },
  { icon: Brain, label: "Building Animation Code", description: "Mapping relationships and composing scenes…", statusKey: "building" },
  { icon: Film, label: "Rendering Animation", description: "Composing your cinematic explanation…", statusKey: "rendering" },
];

const STATUS_TO_STEP: Record<string, number> = {
  queued: 0,
  extracting: 0,
  building: 1,
  rendering: 2,
  completed: 3,
};

const Generation = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const jobId = (location.state as { job_id?: string; filename?: string } | null)?.job_id ?? null;
  const filename = (location.state as { job_id?: string; filename?: string } | null)?.filename ?? "";

  const [activeStep, setActiveStep] = useState(0);
  const [progress, setProgress] = useState(0);
  const [statusMsg, setStatusMsg] = useState("Starting pipeline…");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!jobId) {
      navigate("/dashboard");
      return;
    }

    const poll = async () => {
      try {
        const status: JobStatus = await pollStatus(jobId);
        const step = STATUS_TO_STEP[status.status] ?? 0;
        setActiveStep(step);
        setProgress(Math.min(((step) / 3) * 100 + (status.status === "completed" ? 33 : 10), 100));
        setStatusMsg(status.message || status.status);

        if (status.status === "completed") {
          if (intervalRef.current) clearInterval(intervalRef.current);
          setProgress(100);
          setTimeout(() => navigate("/player", { state: { job_id: jobId } }), 1000);
        } else if (status.status === "failed") {
          if (intervalRef.current) clearInterval(intervalRef.current);
          setErrorMsg(status.error ?? "Generation failed. Please try again.");
        }
      } catch {
        setStatusMsg("Waiting for backend…");
      }
    };

    poll();
    intervalRef.current = setInterval(poll, 4000);
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [jobId, navigate]);

  return (
    <div className="min-h-screen flex items-center justify-center relative overflow-hidden">
      <div className="absolute inset-0 bg-background" />
      <div className="absolute inset-0 magical-glow-overlay opacity-60" />
      <FloatingParticles />

      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="relative z-10 text-center max-w-xl sm:max-w-2xl lg:max-w-3xl mx-auto px-5 sm:px-8"
      >
        <motion.h1
          className="font-heading text-3xl sm:text-4xl lg:text-5xl text-gold-gradient mb-3 sm:mb-4"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
        >
          Transmuting Manuscript…
        </motion.h1>
        {filename && (
          <p className="text-primary/70 text-sm sm:text-base mb-2 font-body truncate">{filename}</p>
        )}
        <p className="text-muted-foreground text-base sm:text-lg mb-12 sm:mb-16">
          {errorMsg ? "Something went wrong." : "Your knowledge is being woven into understanding."}
        </p>

        {errorMsg ? (
          <div className="flex items-start gap-4 p-5 rounded-xl bg-red-500/10 border border-red-500/30 text-left">
            <AlertCircle className="w-6 h-6 text-red-400 flex-shrink-0 mt-0.5" />
            <div>
              <p className="font-heading text-red-400 tracking-wider mb-1">Generation Failed</p>
              <p className="text-sm text-muted-foreground font-body">{errorMsg}</p>
              <button
                onClick={() => navigate("/dashboard")}
                className="mt-4 text-sm text-primary underline font-body"
              >
                ← Back to Dashboard
              </button>
            </div>
          </div>
        ) : (
          <>
            <div className="mb-4">
              <Progress value={progress} className="h-2 bg-secondary" />
              <p className="mt-2 text-xs text-muted-foreground font-body">{statusMsg}</p>
            </div>

            <div className="space-y-4 sm:space-y-6 mt-10 sm:mt-12">
              {STEPS.map((step, i) => {
                const isActive = i === activeStep && activeStep < 3;
                const isDone = i < activeStep;
                const Icon = step.icon;

                return (
                  <motion.div
                    key={step.label}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.15, duration: 0.5 }}
                    className={`flex items-center gap-4 sm:gap-6 p-4 sm:p-6 rounded-xl transition-all duration-500 ${
                      isActive
                        ? "glass-panel gold-glow-sm"
                        : isDone
                        ? "glass-panel opacity-60"
                        : "opacity-30"
                    }`}
                  >
                    <div
                      className={`w-12 h-12 sm:w-14 sm:h-14 rounded-full flex items-center justify-center transition-all duration-500 flex-shrink-0 ${
                        isActive
                          ? "bg-primary/20 text-primary"
                          : isDone
                          ? "bg-accent/20 text-accent"
                          : "bg-secondary text-muted-foreground"
                      }`}
                    >
                      {isDone ? <Check className="w-6 h-6 sm:w-7 sm:h-7" /> : <Icon className="w-6 h-6 sm:w-7 sm:h-7" />}
                    </div>
                    <div className="text-left">
                      <p className={`font-heading text-base sm:text-lg tracking-wider ${isActive ? "text-primary" : isDone ? "text-accent" : "text-muted-foreground"}`}>
                        {step.label}
                      </p>
                      <p className="text-sm sm:text-base text-muted-foreground mt-1">{step.description}</p>
                    </div>
                    {isActive && (
                      <motion.div
                        className="ml-auto w-3 h-3 sm:w-4 sm:h-4 rounded-full bg-primary flex-shrink-0"
                        animate={{ opacity: [1, 0.3, 1] }}
                        transition={{ duration: 1.5, repeat: Infinity }}
                      />
                    )}
                  </motion.div>
                );
              })}
            </div>
          </>
        )}
      </motion.div>
    </div>
  );
};

export default Generation;
