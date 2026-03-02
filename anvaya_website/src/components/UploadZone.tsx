import { useState, useCallback } from "react";
import { motion } from "framer-motion";
import { Upload, FileText } from "lucide-react";
import { cn } from "@/lib/utils";

interface UploadZoneProps {
  onFileChange?: (file: File | null) => void;
}

const UploadZone = ({ onFileChange }: UploadZoneProps) => {
  const [isDragging, setIsDragging] = useState(false);
  const [file, setFile] = useState<File | null>(null);

  const setAndNotify = useCallback((f: File | null) => {
    setFile(f);
    onFileChange?.(f);
  }, [onFileChange]);

  const handleDrag = useCallback((e: React.DragEvent, entering: boolean) => {
    e.preventDefault();
    setIsDragging(entering);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const f = e.dataTransfer.files[0];
    if (f) setAndNotify(f);
  }, [setAndNotify]);

  return (
    <motion.div
      onDragEnter={(e) => handleDrag(e, true)}
      onDragOver={(e) => handleDrag(e, true)}
      onDragLeave={(e) => handleDrag(e, false)}
      onDrop={handleDrop}
      animate={isDragging ? { scale: 1.02 } : { scale: 1 }}
      className={cn(
        "relative rounded-2xl border-2 border-dashed p-10 text-center transition-all duration-300 cursor-pointer",
        isDragging
          ? "border-primary/60 bg-primary/5 gold-glow-sm"
          : "border-border/30 hover:border-primary/30"
      )}
      onClick={() => {
        const input = document.createElement("input");
        input.type = "file";
        input.accept = ".pdf,.doc,.docx,.txt";
        input.onchange = (e) => {
          const f = (e.target as HTMLInputElement).files?.[0];
          if (f) setAndNotify(f);
        };
        input.click();
      }}
    >
      {file ? (
        <div className="flex flex-col items-center gap-3">
          <FileText className="w-10 h-10 text-primary" />
          <p className="text-foreground font-medium">{file.name}</p>
          <p className="text-xs text-muted-foreground">Click to change</p>
        </div>
      ) : (
        <div className="flex flex-col items-center gap-3">
          <Upload className="w-10 h-10 text-muted-foreground" />
          <p className="text-foreground font-heading tracking-wide">Drop Your Manuscript</p>
          <p className="text-xs text-muted-foreground">PDF, DOCX, or TXT</p>
        </div>
      )}
    </motion.div>
  );
};

export default UploadZone;
