"use client";

import { useState } from "react";
import { Calendar, X, ChevronDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

interface DateRangeFilterProps {
  createdAfter: string;
  createdBefore: string;
  onCreatedAfterChange: (date: string) => void;
  onCreatedBeforeChange: (date: string) => void;
  onClear: () => void;
}

// Predefined quick filters
const QUICK_FILTERS = [
  { label: "Today", days: 0 },
  { label: "Last 7 days", days: 7 },
  { label: "Last 30 days", days: 30 },
  { label: "Last 90 days", days: 90 },
  { label: "This year", days: -1 }, // Special case
] as const;

export function DateRangeFilter({
  createdAfter,
  createdBefore,
  onCreatedAfterChange,
  onCreatedBeforeChange,
  onClear,
}: DateRangeFilterProps) {
  const [expanded, setExpanded] = useState(false);

  const hasDateFilter = createdAfter || createdBefore;

  const applyQuickFilter = (days: number) => {
    const now = new Date();

    if (days === 0) {
      // Today
      const today = now.toISOString().split("T")[0];
      onCreatedAfterChange(today);
      onCreatedBeforeChange("");
    } else if (days === -1) {
      // This year
      const yearStart = new Date(now.getFullYear(), 0, 1);
      onCreatedAfterChange(yearStart.toISOString().split("T")[0]);
      onCreatedBeforeChange("");
    } else {
      const past = new Date(now.getTime() - days * 24 * 60 * 60 * 1000);
      onCreatedAfterChange(past.toISOString().split("T")[0]);
      onCreatedBeforeChange("");
    }
  };

  const getFilterLabel = () => {
    if (!hasDateFilter) return "Filter by date";

    if (createdAfter && createdBefore) {
      return `${formatDate(createdAfter)} - ${formatDate(createdBefore)}`;
    } else if (createdAfter) {
      return `From ${formatDate(createdAfter)}`;
    } else if (createdBefore) {
      return `Until ${formatDate(createdBefore)}`;
    }
    return "Date filter";
  };

  const formatDate = (date: string) => {
    try {
      return new Date(date).toLocaleDateString("it-IT", {
        day: "numeric",
        month: "short",
      });
    } catch {
      return date;
    }
  };

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <Button
          variant={hasDateFilter ? "secondary" : "outline"}
          size="sm"
          onClick={() => setExpanded(!expanded)}
          className={cn("gap-2", hasDateFilter && "pr-2")}
        >
          <Calendar className="h-4 w-4" />
          <span className="hidden sm:inline">{getFilterLabel()}</span>
          <span className="sm:hidden">
            {hasDateFilter ? "Date" : "Date"}
          </span>
          <ChevronDown className={cn(
            "h-3 w-3 transition-transform",
            expanded && "rotate-180"
          )} />
        </Button>

        {hasDateFilter && (
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            onClick={(e) => {
              e.stopPropagation();
              onClear();
            }}
            title="Clear date filter"
          >
            <X className="h-4 w-4" />
          </Button>
        )}
      </div>

      {expanded && (
        <div className="rounded-md border p-3 space-y-3 bg-card">
          {/* Quick filters */}
          <div className="space-y-1.5">
            <Label className="text-xs text-muted-foreground">Quick select</Label>
            <div className="flex flex-wrap gap-1.5">
              {QUICK_FILTERS.map((filter) => (
                <Button
                  key={filter.label}
                  variant="outline"
                  size="sm"
                  className="h-7 text-xs"
                  onClick={() => applyQuickFilter(filter.days)}
                >
                  {filter.label}
                </Button>
              ))}
            </div>
          </div>

          {/* Custom date inputs */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="date-from" className="text-xs text-muted-foreground">
                From
              </Label>
              <Input
                id="date-from"
                type="date"
                value={createdAfter}
                onChange={(e) => onCreatedAfterChange(e.target.value)}
                className="h-8"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="date-to" className="text-xs text-muted-foreground">
                To
              </Label>
              <Input
                id="date-to"
                type="date"
                value={createdBefore}
                onChange={(e) => onCreatedBeforeChange(e.target.value)}
                className="h-8"
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
