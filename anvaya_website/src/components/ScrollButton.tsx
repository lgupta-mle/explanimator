import { cn } from "@/lib/utils";
import { motion } from "framer-motion";
import { ButtonHTMLAttributes, forwardRef } from "react";
import scrollBg from "@/assets/scroll.png";

interface ScrollButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {}

const ScrollButton = forwardRef<HTMLButtonElement, ScrollButtonProps>(
  ({ className, children, ...props }, ref) => {
    return (
      <motion.button
        ref={ref}
        whileHover={{ scale: 1.06, filter: "brightness(1.15) drop-shadow(0 0 20px hsla(38, 65%, 65%, 0.5))" }}
        whileTap={{ scale: 0.97 }}
        className={cn(
          "relative group cursor-pointer font-heading tracking-[0.15em] uppercase text-base md:text-lg",
          className
        )}
        {...(props as any)}
      >
        <div className="relative w-[320px] md:w-[400px] h-[90px] md:h-[110px] flex items-center justify-center">
          <img
            src={scrollBg}
            alt=""
            className="absolute inset-0 w-full h-full object-contain pointer-events-none select-none"
            draggable={false}
          />
          <span
            className="relative z-10 font-heading text-sm md:text-base tracking-[0.2em] uppercase"
            style={{ color: "#3a2a10" }}
          >
            {children}
          </span>
        </div>
      </motion.button>
    );
  }
);
ScrollButton.displayName = "ScrollButton";

export default ScrollButton;
