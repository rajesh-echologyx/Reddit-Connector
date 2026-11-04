import type { InputHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        "flex h-10 w-full rounded-md border border-[var(--color-line)] bg-white/80 px-3 py-2 text-sm outline-none focus:border-[var(--color-moss)]",
        className,
      )}
      {...props}
    />
  );
}
