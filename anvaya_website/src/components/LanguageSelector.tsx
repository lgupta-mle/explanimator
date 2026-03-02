import { Globe } from "lucide-react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const languages = [
  { value: "en", label: "English" },
  { value: "hi", label: "हिन्दी" },
  { value: "zh", label: "中文" },
];

interface Props {
  value?: string;
  onChange?: (val: string) => void;
}

const LanguageSelector = ({ value = "en", onChange }: Props) => (
  <Select value={value} onValueChange={onChange}>
    <SelectTrigger className="glass-panel border-border/30 hover:border-primary/40 transition-colors w-full">
      <div className="flex items-center gap-2">
        <Globe className="w-4 h-4 text-primary" />
        <SelectValue />
      </div>
    </SelectTrigger>
    <SelectContent className="bg-card border-border/30">
      {languages.map((lang) => (
        <SelectItem key={lang.value} value={lang.value} className="hover:bg-primary/10 focus:bg-primary/10">
          {lang.label}
        </SelectItem>
      ))}
    </SelectContent>
  </Select>
);

export default LanguageSelector;
