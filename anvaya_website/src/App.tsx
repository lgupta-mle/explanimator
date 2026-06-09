import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import Index from "./pages/Index";
import Dashboard from "./pages/Dashboard";
import Generation from "./pages/Generation";
import Player from "./pages/Player";
import Videos from "./pages/Videos";
import Tokens from "./pages/Tokens";
import Feedback from "./pages/Feedback";
import NotFound from "./pages/NotFound";
import CursorHalo from "./components/CursorHalo";

const queryClient = new QueryClient();

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <CursorHalo />
      <Toaster />
      <Sonner />
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Index />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/generation" element={<Generation />} />
          <Route path="/player" element={<Player />} />
          <Route path="/videos" element={<Videos />} />
          <Route path="/tokens" element={<Tokens />} />
          <Route path="/feedback" element={<Feedback />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
