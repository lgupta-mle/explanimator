import { motion } from "framer-motion";
import { useNavigate } from "react-router-dom";
import { SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import DashboardSidebar from "@/components/DashboardSidebar";
import GlassPanel from "@/components/GlassPanel";
import FloatingParticles from "@/components/FloatingParticles";
import { Play, Clock, Sparkles, Layers } from "lucide-react";
import { loadVideos, formatDuration, type SavedVideo } from "@/lib/videoStorage";

const Videos = () => {
  const navigate = useNavigate();
  const videos: SavedVideo[] = loadVideos();

  const handleOpen = (video: SavedVideo) => {
    navigate("/player", { state: { job_id: video.job_id } });
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
              My Videos
            </span>
          </header>

          <main className="flex-1 p-4 sm:p-8 lg:p-12 overflow-auto">
            <div className="max-w-5xl mx-auto space-y-8 sm:space-y-10">
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6 }}
              >
                <h1 className="font-heading text-3xl sm:text-4xl lg:text-5xl text-gold-gradient mb-3 sm:mb-4">My Videos</h1>
                <p className="text-muted-foreground text-base sm:text-lg">Your previously generated lectures.</p>
              </motion.div>

              {videos.length === 0 ? (
                <GlassPanel className="text-center py-16 sm:py-24 px-6 sm:px-8">
                  <Sparkles className="w-12 h-12 sm:w-14 sm:h-14 text-primary/40 mx-auto mb-5 sm:mb-6" />
                  <p className="text-muted-foreground font-body text-base sm:text-lg">No videos yet. Generate your first lecture from the Dashboard.</p>
                </GlassPanel>
              ) : (
                videos.map((video, i) => (
                  <motion.div
                    key={video.job_id}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.5, delay: i * 0.1 }}
                  >
                    <GlassPanel
                      className="flex items-center gap-5 sm:gap-8 p-5 sm:p-8 cursor-pointer group hover:border-primary/40 transition-all duration-300"
                      onClick={() => handleOpen(video)}
                    >
                      <div className="w-14 h-14 sm:w-20 sm:h-20 rounded-xl sm:rounded-2xl bg-primary/10 flex items-center justify-center group-hover:bg-primary/20 group-hover:shadow-[0_0_25px_hsla(38,65%,65%,0.25)] transition-all duration-300 flex-shrink-0">
                        <Play className="w-6 h-6 sm:w-9 sm:h-9 text-primary" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <h3 className="font-heading text-base sm:text-xl tracking-wider text-foreground mb-1 sm:mb-2 truncate">{video.paper_title}</h3>
                        <div className="flex flex-wrap items-center gap-3 sm:gap-5 text-sm sm:text-base text-muted-foreground">
                          <span>{video.date}</span>
                          <span className="text-primary/60 hidden sm:inline">·</span>
                          <span className="flex items-center gap-1.5">
                            <Clock className="w-4 h-4" /> {formatDuration(video.duration_seconds)}
                          </span>
                          <span className="text-primary/60 hidden sm:inline">·</span>
                          <span className="flex items-center gap-1.5">
                            <Layers className="w-4 h-4" /> {video.segments_count} section{video.segments_count !== 1 ? "s" : ""}
                          </span>
                        </div>
                      </div>
                    </GlassPanel>
                  </motion.div>
                ))
              )}
            </div>
          </main>
        </div>
      </div>
    </SidebarProvider>
  );
};

export default Videos;
