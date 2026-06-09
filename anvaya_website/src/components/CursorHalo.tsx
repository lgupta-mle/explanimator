import { useEffect, useState } from "react";

const CursorHalo = () => {
  const [pos, setPos] = useState({ x: -100, y: -100 });

  useEffect(() => {
    const handleMove = (e: MouseEvent) => {
      setPos({ x: e.clientX, y: e.clientY });
    };
    window.addEventListener("mousemove", handleMove);
    return () => window.removeEventListener("mousemove", handleMove);
  }, []);

  return (
    <div
      className="pointer-events-none fixed z-[9999] rounded-full transition-transform duration-75"
      style={{
        left: pos.x - 20,
        top: pos.y - 20,
        width: 40,
        height: 40,
        background: "radial-gradient(circle, hsla(38, 65%, 65%, 0.18) 0%, transparent 70%)",
        boxShadow: "0 0 20px 4px hsla(38, 65%, 65%, 0.08)",
      }}
    />
  );
};

export default CursorHalo;
