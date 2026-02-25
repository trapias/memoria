"use client";

import { ArrowUp, ArrowDown, ArrowUpDown } from "lucide-react";
import { cn } from "@/lib/utils";

export type SortDir = "asc" | "desc";

interface SortableHeaderProps {
  label: string;
  field: string;
  currentField: string;
  currentDir: SortDir;
  onSort: (field: string, dir: SortDir) => void;
  className?: string;
}

export function SortableHeader({
  label,
  field,
  currentField,
  currentDir,
  onSort,
  className,
}: SortableHeaderProps) {
  const isActive = currentField === field;

  function handleClick() {
    if (isActive) {
      onSort(field, currentDir === "asc" ? "desc" : "asc");
    } else {
      onSort(field, "asc");
    }
  }

  return (
    <th
      className={cn(
        "px-4 py-3 font-medium select-none cursor-pointer hover:bg-muted/80 transition-colors",
        className
      )}
      onClick={handleClick}
    >
      <span className="inline-flex items-center gap-1">
        {label}
        {isActive ? (
          currentDir === "asc" ? (
            <ArrowUp className="h-3.5 w-3.5" />
          ) : (
            <ArrowDown className="h-3.5 w-3.5" />
          )
        ) : (
          <ArrowUpDown className="h-3.5 w-3.5 text-muted-foreground/40" />
        )}
      </span>
    </th>
  );
}
