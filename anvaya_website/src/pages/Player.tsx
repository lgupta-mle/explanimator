import { useState, useEffect, useRef } from "react";
import { motion } from "framer-motion";
import { useLocation } from "react-router-dom";
import { SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import DashboardSidebar from "@/components/DashboardSidebar";
import GlassPanel from "@/components/GlassPanel";
import FloatingParticles from "@/components/FloatingParticles";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Play, Pause, Volume2, Maximize, BookOpen, List, MessageSquare, Loader2 } from "lucide-react";
import { getResult, videoURL, type JobResult, type Segment } from "@/services/api";
import { saveVideo } from "@/lib/videoStorage";

const formatTime = (secs: number) => {
  const m = Math.floor(secs / 60);
  const s = Math.floor(secs % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
};

const Player = () => {
  const location = useLocation();
  const jobId = (location.state as { job_id?: string } | null)?.job_id ?? null;

  const videoRef = useRef<HTMLVideoElement>(null);
  const activeTranscriptRef = useRef<HTMLParagraphElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [activeSegmentIdx, setActiveSegmentIdx] = useState<number | null>(null);

  const [result, setResult] = useState<JobResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    if (!jobId) {
      setLoading(false);
      return;
    }
    getResult(jobId)
      .then((r) => {
        setResult(r);
        setLoading(false);
        if (jobId) saveVideo(jobId, r);
      })
      .catch((e) => { setLoadError(e.message); setLoading(false); });
  }, [jobId]);

  const segments: Segment[] = result?.segments ?? [];
  const paperTitle = result?.paper_title ?? "Video Player";

  // Determine which segment is currently being spoken
  const activeSpeakingIdx = segments.findIndex(
    (s) => currentTime >= s.start_time && currentTime < s.start_time + s.duration
  );

  // Auto-scroll active transcript paragraph into view
  useEffect(() => {
    if (activeTranscriptRef.current) {
      activeTranscriptRef.current.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }, [activeSpeakingIdx]);

  const togglePlay = () => {
    const v = videoRef.current;
    if (!v) return;
    if (v.paused) { v.play(); setIsPlaying(true); }
    else { v.pause(); setIsPlaying(false); }
  };

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const v = videoRef.current;
    if (!v) return;
    const t = (parseFloat(e.target.value) / 100) * duration;
    v.currentTime = t;
    setCurrentTime(t);
  };

  const seekToSegment = (seg: Segment, idx: number) => {
    setActiveSegmentIdx(idx === activeSegmentIdx ? null : idx);
    const v = videoRef.current;
    if (v && duration > 0) {
      v.currentTime = seg.start_time;
      setCurrentTime(seg.start_time);
    }
  };

  const progressPct = duration > 0 ? (currentTime / duration) * 100 : 0;

  return (
    <SidebarProvider>
      <div className="min-h-screen flex w-full relative">
        <FloatingParticles />
        <div className="absolute inset-0 magical-glow-overlay pointer-events-none" />
        <DashboardSidebar />

        <div className="flex-1 flex flex-col relative z-10">
          <header className="h-16 sm:h-20 flex items-center border-b border-border/20 px-4 sm:px-8">
            <SidebarTrigger className="text-muted-foreground hover:text-primary" />
            <span className="ml-4 sm:ml-6 font-heading text-base sm:text-lg tracking-[0.15em] text-primary truncate">
              {loading ? "Video Player" : paperTitle}
            </span>
          </header>

          <main className="flex-1 p-4 sm:p-6 lg:p-10 overflow-auto">
            <div className="max-w-5xl mx-auto space-y-6">

              {/* Video Player */}
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6 }}
              >
                <GlassPanel className="p-0 overflow-hidden">
                  <div className="relative aspect-video bg-background/50 flex items-center justify-center">
                    {loading ? (
                      <Loader2 className="w-12 h-12 text-primary animate-spin" />
                    ) : loadError ? (
                      <p className="text-muted-foreground font-body text-sm px-6 text-center">{loadError}</p>
                    ) : result ? (
                      <video
                        ref={videoRef}
                        src={videoURL(jobId!)}
                        className="w-full h-full object-contain"
                        onTimeUpdate={() => setCurrentTime(videoRef.current?.currentTime ?? 0)}
                        onLoadedMetadata={() => setDuration(videoRef.current?.duration ?? 0)}
                        onPlay={() => setIsPlaying(true)}
                        onPause={() => setIsPlaying(false)}
                        onEnded={() => setIsPlaying(false)}
                      />
                    ) : (
                      <>
                        <div className="absolute inset-0 bg-gradient-to-t from-background/40 to-transparent" />
                        <button
                          onClick={togglePlay}
                          className="relative z-10 w-20 h-20 sm:w-28 sm:h-28 rounded-full bg-primary/20 border border-primary/40 flex items-center justify-center hover:bg-primary/30 transition-all hover:shadow-[0_0_40px_hsla(38,65%,65%,0.5)]"
                        >
                          <Play className="w-8 h-8 sm:w-12 sm:h-12 text-primary ml-1" />
                        </button>
                      </>
                    )}
                  </div>

                  {/* Controls */}
                  <div className="px-4 sm:px-6 py-4 flex items-center gap-3 sm:gap-5 border-t border-border/20">
                    <button onClick={togglePlay} className="text-primary hover:text-gold-soft transition-colors flex-shrink-0">
                      {isPlaying ? <Pause className="w-5 h-5 sm:w-6 sm:h-6" /> : <Play className="w-5 h-5 sm:w-6 sm:h-6" />}
                    </button>
                    <input
                      type="range"
                      min={0}
                      max={100}
                      value={progressPct}
                      onChange={handleSeek}
                      className="flex-1 h-1.5 accent-primary cursor-pointer"
                    />
                    <span className="text-sm sm:text-base text-muted-foreground font-body whitespace-nowrap flex-shrink-0">
                      {formatTime(currentTime)} / {formatTime(duration)}
                    </span>
                    <Volume2 className="w-5 h-5 sm:w-6 sm:h-6 text-muted-foreground hover:text-foreground cursor-pointer transition-colors hidden sm:block flex-shrink-0" />
                    <button
                      onClick={() => videoRef.current?.requestFullscreen()}
                      className="flex-shrink-0"
                    >
                      <Maximize className="w-5 h-5 sm:w-6 sm:h-6 text-muted-foreground hover:text-foreground cursor-pointer transition-colors" />
                    </button>
                  </div>
                </GlassPanel>
              </motion.div>

              {/* Tabs panel */}
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, delay: 0.15 }}
              >
                <GlassPanel className="p-4 sm:p-6 lg:p-8 max-h-[50vh] overflow-hidden flex flex-col">
                  <Tabs defaultValue="content" className="w-full flex flex-col flex-1 min-h-0">
                    <TabsList className="bg-secondary/50 w-full sm:w-auto h-12 sm:h-14 flex-shrink-0">
                      <TabsTrigger value="transcript" className="flex-1 sm:flex-none gap-2 text-sm sm:text-base px-4 sm:px-6 data-[state=active]:text-primary">
                        <BookOpen className="w-4 h-4 sm:w-5 sm:h-5" />
                        Transcript
                      </TabsTrigger>
                      <TabsTrigger value="content" className="flex-1 sm:flex-none gap-2 text-sm sm:text-base px-4 sm:px-6 data-[state=active]:text-primary">
                        <List className="w-4 h-4 sm:w-5 sm:h-5" />
                        Content
                      </TabsTrigger>
                      <TabsTrigger value="qa" className="flex-1 sm:flex-none gap-2 text-sm sm:text-base px-4 sm:px-6 data-[state=active]:text-primary">
                        <MessageSquare className="w-4 h-4 sm:w-5 sm:h-5" /> Q&A
                      </TabsTrigger>
                    </TabsList>

                    {/* Transcript — per-segment with live highlighting */}
                    <TabsContent value="transcript" className="mt-6 sm:mt-8 overflow-y-auto flex-1 min-h-0">
                      {loading ? (
                        <div className="flex items-center gap-3 text-muted-foreground font-body">
                          <Loader2 className="w-4 h-4 animate-spin" /> Loading transcript…
                        </div>
                      ) : segments.length > 0 ? (
                        <div className="space-y-6 max-w-3xl">
                          {segments.map((seg, i) => {
                            const isActive = i === activeSpeakingIdx;
                            return (
                              <p
                                key={i}
                                ref={isActive ? activeTranscriptRef : null}
                                className={`font-body leading-relaxed text-base sm:text-lg transition-colors duration-300 cursor-pointer ${
                                  isActive
                                    ? "text-primary"
                                    : "text-foreground/35 hover:text-foreground/60"
                                }`}
                                onClick={() => {
                                  const v = videoRef.current;
                                  if (v) { v.currentTime = seg.start_time; setCurrentTime(seg.start_time); }
                                }}
                              >
                                {seg.narration_clean || seg.narration_script}
                              </p>
                            );
                          })}
                        </div>
                      ) : (
                        <p className="text-muted-foreground font-body">No transcript available.</p>
                      )}
                    </TabsContent>

                    {/* Content — section titles with timestamps */}
                    <TabsContent value="content" className="mt-6 sm:mt-8 overflow-y-auto flex-1 min-h-0">
                      {loading ? (
                        <div className="flex items-center gap-3 text-muted-foreground font-body">
                          <Loader2 className="w-4 h-4 animate-spin" /> Loading content…
                        </div>
                      ) : segments.length > 0 ? (
                        <div className="space-y-3 sm:space-y-4">
                          {segments.map((seg, idx) => (
                            <button
                              key={idx}
                              onClick={() => seekToSegment(seg, idx)}
                              className={`w-full text-left p-4 sm:p-5 rounded-xl transition-all duration-300 ${
                                activeSegmentIdx === idx
                                  ? "bg-primary/15 border border-primary/30 gold-glow-sm"
                                  : "bg-secondary/30 border border-transparent hover:border-primary/20 hover:bg-primary/5"
                              }`}
                            >
                              <div className="flex justify-between items-center">
                                <span className="font-heading text-sm sm:text-base tracking-wider text-foreground">{seg.title}</span>
                                <span className="text-sm sm:text-base text-primary font-body flex-shrink-0 ml-3">{seg.timestamp}</span>
                              </div>
                              {activeSegmentIdx === idx && (
                                <motion.p
                                  initial={{ opacity: 0, height: 0 }}
                                  animate={{ opacity: 1, height: "auto" }}
                                  className="text-sm sm:text-base text-muted-foreground mt-3 sm:mt-4 font-body leading-relaxed line-clamp-4"
                                >
                                  {seg.narration_script}
                                </motion.p>
                              )}
                            </button>
                          ))}
                        </div>
                      ) : (
                        <p className="text-muted-foreground font-body">No content sections available.</p>
                      )}
                    </TabsContent>

                    {/* Q&A */}
                    <TabsContent value="qa" className="mt-6 sm:mt-8 overflow-y-auto flex-1 min-h-0">
                      <div className="flex flex-col min-h-[200px] sm:min-h-[250px]">
                        <div className="flex-1 flex items-center justify-center text-muted-foreground text-base sm:text-lg font-body">
                          <p>Ask a question about this video…</p>
                        </div>
                        <div className="flex gap-3 mt-4">
                          <input
                            type="text"
                            placeholder="Type your question…"
                            className="flex-1 bg-secondary/50 border border-border/30 rounded-xl px-4 sm:px-5 py-3 sm:py-4 text-base sm:text-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary/40 font-body"
                          />
                          <button className="px-5 sm:px-8 py-3 sm:py-4 bg-primary/20 text-primary border border-primary/40 rounded-xl text-sm sm:text-base font-heading tracking-wider hover:bg-primary/30 transition-colors whitespace-nowrap">
                            Ask
                          </button>
                        </div>
                      </div>
                    </TabsContent>
                  </Tabs>
                </GlassPanel>
              </motion.div>

            </div>
          </main>
        </div>
      </div>
    </SidebarProvider>
  );
};

export default Player;
