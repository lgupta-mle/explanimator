import { motion } from "framer-motion";
import { SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import DashboardSidebar from "@/components/DashboardSidebar";
import GlassPanel from "@/components/GlassPanel";
import FloatingParticles from "@/components/FloatingParticles";
import MagicalButton from "@/components/MagicalButton";
import { Zap, TrendingUp, Calendar } from "lucide-react";

const Tokens = () => {
  const used = 3;
  const total = 5;
  const percentage = (used / total) * 100;
  const remaining = total - used;

  const radius = 90;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (percentage / 100) * circumference;

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
              Tokens
            </span>
          </header>

          <main className="flex-1 p-4 sm:p-6 lg:p-8 overflow-auto flex items-center justify-center">
            <div className="max-w-2xl w-full">
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6 }}
              >
                <h1 className="font-heading text-2xl sm:text-3xl lg:text-4xl text-gold-gradient mb-2 sm:mb-3 text-center">Token Balance</h1>
                <p className="text-muted-foreground text-sm sm:text-base text-center mb-6 sm:mb-8">
                  Each generation consumes one token.
                </p>
              </motion.div>

              <motion.div
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.8, delay: 0.2 }}
              >
                <GlassPanel className="flex flex-col items-center py-6 sm:py-10 lg:py-12 px-4 sm:px-8">
                  {/* Circular meter */}
                  <div className="relative w-36 h-36 sm:w-48 sm:h-48 lg:w-56 lg:h-56 mb-6 sm:mb-8">
                    <svg className="w-full h-full -rotate-90" viewBox="0 0 220 220">
                      <circle
                        cx="110" cy="110" r={radius}
                        fill="none"
                        stroke="hsl(var(--secondary))"
                        strokeWidth="12"
                      />
                      <motion.circle
                        cx="110" cy="110" r={radius}
                        fill="none"
                        stroke="hsl(var(--primary))"
                        strokeWidth="12"
                        strokeLinecap="round"
                        strokeDasharray={circumference}
                        initial={{ strokeDashoffset: circumference }}
                        animate={{ strokeDashoffset }}
                        transition={{ duration: 1.5, delay: 0.5, ease: "easeOut" }}
                        style={{ filter: "drop-shadow(0 0 12px hsla(38, 65%, 65%, 0.5))" }}
                      />
                    </svg>
                    <div className="absolute inset-0 flex flex-col items-center justify-center">
                      <span className="font-heading text-4xl sm:text-5xl lg:text-6xl text-primary">{remaining}</span>
                      <span className="text-xs sm:text-sm text-muted-foreground font-body mt-1 sm:mt-2">of {total} remaining</span>
                    </div>
                  </div>

                  {/* Stats row */}
                  <div className="grid grid-cols-3 gap-3 sm:gap-6 w-full mb-6 sm:mb-8">
                    <div className="text-center">
                      <Zap className="w-5 h-5 sm:w-6 sm:h-6 text-primary mx-auto mb-1 sm:mb-2" />
                      <p className="text-xl sm:text-2xl lg:text-3xl font-heading text-foreground">{used}</p>
                      <p className="text-xs sm:text-sm text-muted-foreground mt-0.5 sm:mt-1">Used</p>
                    </div>
                    <div className="text-center">
                      <TrendingUp className="w-5 h-5 sm:w-6 sm:h-6 text-accent mx-auto mb-1 sm:mb-2" />
                      <p className="text-xl sm:text-2xl lg:text-3xl font-heading text-foreground">{remaining}</p>
                      <p className="text-xs sm:text-sm text-muted-foreground mt-0.5 sm:mt-1">Remaining</p>
                    </div>
                    <div className="text-center">
                      <Calendar className="w-5 h-5 sm:w-6 sm:h-6 text-primary mx-auto mb-1 sm:mb-2" />
                      <p className="text-xl sm:text-2xl lg:text-3xl font-heading text-foreground">{total}</p>
                      <p className="text-xs sm:text-sm text-muted-foreground mt-0.5 sm:mt-1">Monthly</p>
                    </div>
                  </div>

                  <MagicalButton
                    variant="primary"
                    size="md"
                    className="border-accent/40 bg-accent/20 text-accent hover:bg-accent/30 hover:shadow-[0_0_25px_hsla(160,25%,38%,0.4)] font-bold text-sm sm:text-base"
                  >
                    Upgrade Plan
                  </MagicalButton>
                </GlassPanel>
              </motion.div>
            </div>
          </main>
        </div>
      </div>
    </SidebarProvider>
  );
};

export default Tokens;
