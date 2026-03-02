import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import DashboardSidebar from "@/components/DashboardSidebar";
import GlassPanel from "@/components/GlassPanel";
import FloatingParticles from "@/components/FloatingParticles";
import MagicalButton from "@/components/MagicalButton";
import { Textarea } from "@/components/ui/textarea";
import { CheckCircle } from "lucide-react";

const difficultyOptions = ["Too Easy", "Just Right", "A Bit Hard", "Too Difficult"];
const clarityOptions = ["Not at All", "Somewhat", "Mostly", "Perfectly Clear"];

const TextButtonRating = ({
  value,
  onChange,
  label,
  options,
}: {
  value: number | null;
  onChange: (v: number) => void;
  label: string;
  options: string[];
}) => (
  <div>
    <p className="font-heading text-base sm:text-lg tracking-wider text-primary mb-4 sm:mb-5">{label}</p>
    <div className="flex flex-wrap gap-2 sm:gap-3">
      {options.map((option, i) => (
        <motion.button
          key={i}
          whileHover={{ scale: 1.04 }}
          whileTap={{ scale: 0.96 }}
          onClick={() => onChange(i)}
          className={`px-4 sm:px-6 py-2.5 sm:py-3 rounded-xl text-sm sm:text-base font-body font-medium tracking-wide transition-all duration-300 border ${
            value === i
              ? "bg-primary/20 border-primary/50 text-primary gold-glow-sm"
              : "bg-secondary/30 border-border/20 text-muted-foreground hover:border-primary/30 hover:bg-primary/5 hover:text-foreground"
          }`}
        >
          {option}
        </motion.button>
      ))}
    </div>
  </div>
);

const Feedback = () => {
  const [levelRating, setLevelRating] = useState<number | null>(null);
  const [clarityRating, setClarityRating] = useState<number | null>(null);
  const [suggestion, setSuggestion] = useState("");
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = () => setSubmitted(true);

  const handleReset = () => {
    setSubmitted(false);
    setLevelRating(null);
    setClarityRating(null);
    setSuggestion("");
  };

  return (
    <SidebarProvider>
      <div className="min-h-screen flex w-full relative">
        <FloatingParticles />
        <div className="absolute inset-0 magical-glow-overlay pointer-events-none" />
        <DashboardSidebar />

        <div className="flex-1 flex flex-col relative z-10">
          <header className="h-16 sm:h-20 flex items-center border-b border-border/20 px-4 sm:px-8">
            <SidebarTrigger className="text-muted-foreground hover:text-primary" />
            <span className="ml-4 sm:ml-6 font-heading text-base sm:text-lg tracking-[0.15em] text-primary">
              Feedback
            </span>
          </header>

          <main className="flex-1 p-4 sm:p-8 lg:p-12 overflow-auto">
            <div className="max-w-2xl mx-auto">
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6 }}
              >
                <h1 className="font-heading text-3xl sm:text-4xl lg:text-5xl text-gold-gradient mb-3 sm:mb-4 text-center font-semibold">Share Your Thoughts</h1>
                <p className="text-muted-foreground text-base sm:text-lg text-center mb-10 sm:mb-14">
                  Help us refine the academy experience.
                </p>
              </motion.div>

              <AnimatePresence mode="wait">
                {submitted ? (
                  <motion.div
                    key="success"
                    initial={{ opacity: 0, scale: 0.8 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.8 }}
                    transition={{ duration: 0.5, ease: "easeOut" }}
                  >
                    <GlassPanel className="flex flex-col items-center py-14 sm:py-20 text-center px-6 sm:px-10">
                      <motion.div
                        initial={{ scale: 0 }}
                        animate={{ scale: 1 }}
                        transition={{ delay: 0.2, type: "spring", stiffness: 200, damping: 12 }}
                      >
                        <div className="w-20 h-20 sm:w-24 sm:h-24 rounded-full bg-accent/20 flex items-center justify-center mb-6 sm:mb-8 mx-auto gold-glow">
                          <CheckCircle className="w-10 h-10 sm:w-12 sm:h-12 text-accent" />
                        </div>
                      </motion.div>
                      <motion.h2
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.4 }}
                        className="font-heading text-2xl sm:text-3xl text-gold-gradient mb-3 sm:mb-4 font-semibold"
                      >
                        Thank You!
                      </motion.h2>
                      <motion.p
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.5 }}
                        className="text-muted-foreground text-base sm:text-lg font-body mb-8 sm:mb-10"
                      >
                        Your feedback helps us shape a better learning experience.
                      </motion.p>
                      <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ delay: 0.7 }}
                      >
                        <MagicalButton variant="secondary" size="lg" onClick={handleReset}>
                          Submit Another
                        </MagicalButton>
                      </motion.div>

                      {Array.from({ length: 12 }).map((_, i) => (
                        <motion.div
                          key={i}
                          className="absolute text-xl sm:text-2xl pointer-events-none"
                          initial={{ opacity: 1, x: 0, y: 0 }}
                          animate={{
                            opacity: 0,
                            x: (Math.random() - 0.5) * 300,
                            y: (Math.random() - 0.5) * 300,
                          }}
                          transition={{ duration: 1.2, delay: 0.2 + i * 0.05 }}
                        >
                          {["✨", "🌟", "⭐", "💫"][i % 4]}
                        </motion.div>
                      ))}
                    </GlassPanel>
                  </motion.div>
                ) : (
                  <motion.div
                    key="form"
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -20 }}
                    transition={{ duration: 0.6, delay: 0.15 }}
                  >
                    <GlassPanel className="space-y-10 sm:space-y-12 py-8 sm:py-12 px-5 sm:px-10">
                      <TextButtonRating
                        value={levelRating}
                        onChange={setLevelRating}
                        label="Was the difficulty level appropriate?"
                        options={difficultyOptions}
                      />

                      <TextButtonRating
                        value={clarityRating}
                        onChange={setClarityRating}
                        label="Did this clarify the research?"
                        options={clarityOptions}
                      />

                      <div>
                        <p className="font-heading text-base sm:text-lg tracking-wider text-primary mb-4 sm:mb-5">
                          Suggestions?
                        </p>
                        <Textarea
                          value={suggestion}
                          onChange={(e) => setSuggestion(e.target.value)}
                          placeholder="Share your thoughts…"
                          className="bg-secondary/30 border-border/20 focus:border-primary/40 text-foreground placeholder:text-muted-foreground font-body resize-none min-h-[120px] sm:min-h-[140px] text-base sm:text-lg"
                        />
                      </div>

                      <div className="flex justify-center pt-4 sm:pt-6">
                        <MagicalButton size="lg" onClick={handleSubmit}>
                          Submit Feedback
                        </MagicalButton>
                      </div>
                    </GlassPanel>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </main>
        </div>
      </div>
    </SidebarProvider>
  );
};

export default Feedback;
