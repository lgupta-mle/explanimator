import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import DashboardSidebar from "@/components/DashboardSidebar";
import GlassPanel from "@/components/GlassPanel";
import UploadZone from "@/components/UploadZone";
import DifficultySelector from "@/components/DifficultySelector";
import LanguageSelector from "@/components/LanguageSelector";
import MagicalButton from "@/components/MagicalButton";
import FloatingParticles from "@/components/FloatingParticles";
import { uploadPDF } from "@/services/api";

const Dashboard = () => {
  const [difficulty, setDifficulty] = useState("initiate");
  const [language, setLanguage] = useState("en");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const navigate = useNavigate();

  const handleTransmute = async () => {
    if (!selectedFile) {
      setUploadError("Please select a PDF manuscript first.");
      return;
    }
    setUploadError(null);
    setIsSubmitting(true);
    try {
      const { job_id } = await uploadPDF(selectedFile);
      navigate("/generation", { state: { job_id, filename: selectedFile.name } });
    } catch (err: unknown) {
      setUploadError(err instanceof Error ? err.message : "Upload failed. Is the backend running?");
      setIsSubmitting(false);
    }
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
              Dashboard
            </span>
          </header>

          <main className="flex-1 p-4 sm:p-8 lg:p-12 overflow-auto">
            <div className="max-w-4xl mx-auto space-y-8 sm:space-y-10">
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6 }}
              >
                <h1 className="font-heading text-3xl sm:text-4xl lg:text-5xl text-gold-gradient mb-3 sm:mb-4">
                  Begin Your Study
                </h1>
                <p className="text-muted-foreground text-base sm:text-lg">
                  Upload a manuscript and select your path of understanding.
                </p>
              </motion.div>

              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, delay: 0.15 }}
              >
                <GlassPanel className="p-5 sm:p-8">
                  <h2 className="font-heading text-base sm:text-lg tracking-widest text-primary mb-5 sm:mb-6">Manuscript</h2>
                  <UploadZone onFileChange={setSelectedFile} />
                  {uploadError && (
                    <p className="mt-4 text-sm text-red-400 font-body">{uploadError}</p>
                  )}
                </GlassPanel>
              </motion.div>

              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, delay: 0.3 }}
              >
                <GlassPanel className="p-5 sm:p-8">
                  <h2 className="font-heading text-base sm:text-lg tracking-widest text-primary mb-5 sm:mb-6">Difficulty</h2>
                  <DifficultySelector value={difficulty} onChange={setDifficulty} />
                </GlassPanel>
              </motion.div>

              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, delay: 0.45 }}
              >
                <GlassPanel className="p-5 sm:p-8">
                  <h2 className="font-heading text-base sm:text-lg tracking-widest text-primary mb-5 sm:mb-6">Language</h2>
                  <LanguageSelector value={language} onChange={setLanguage} />
                </GlassPanel>
              </motion.div>

              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, delay: 0.6 }}
                className="flex justify-center pt-4 sm:pt-8"
              >
                <MagicalButton
                  size="lg"
                  className="font-semibold"
                  onClick={handleTransmute}
                  disabled={isSubmitting}
                >
                  {isSubmitting ? "Uploading…" : "Transmute Manuscript"}
                </MagicalButton>
              </motion.div>
            </div>
          </main>
        </div>
      </div>
    </SidebarProvider>
  );
};

export default Dashboard;
