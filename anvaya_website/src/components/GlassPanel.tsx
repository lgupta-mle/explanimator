import { cn } from "@/lib/utils";
import { HTMLAttributes, forwardRef } from "react";

const GlassPanel = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn("glass-panel p-6", className)} {...props} />
  )
);
GlassPanel.displayName = "GlassPanel";

export default GlassPanel;
