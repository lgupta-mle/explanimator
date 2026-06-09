import { useState } from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { Sprout, BookOpen, Wand2 } from "lucide-react";

const levels = [
  { id: "initiate", label: "Initiate", desc: "Learn foundations", icon: Sprout },
  { id: "scholar", label: "Scholar", desc: "Structured deep dive", icon: BookOpen },
];

interface Props {
  value?: string;
  onChange?: (val: string) => void;
}

const DifficultySelector = ({ value, onChange }: Props) => {
  const [selected, setSelected] = useState(value || "initiate");

  const handleSelect = (id: string) => {
    setSelected(id);
    onChange?.(id);
  };

  return (
    <div className="grid grid-cols-2 gap-3">
      {levels.map((level) => {
        const active = selected === level.id;
        return (
          <motion.button
            key={level.id}
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.98 }}
            onClick={() => handleSelect(level.id)}
            className={cn(
              "glass-panel flex flex-col items-center gap-2 p-4 cursor-pointer transition-all duration-300",
              active
                ? "border-primary/60 gold-glow-sm"
                : "border-border/20 hover:border-primary/30"
            )}
          >
            <level.icon className={cn("w-6 h-6 transition-colors", active ? "text-primary" : "text-muted-foreground")} />
            <span className={cn("font-heading text-sm tracking-wide", active ? "text-primary" : "text-foreground")}>
              {level.label}
            </span>
            <span className="text-xs text-muted-foreground text-center">{level.desc}</span>
          </motion.button>
        );
      })}
    </div>
  );
};

export default DifficultySelector;
