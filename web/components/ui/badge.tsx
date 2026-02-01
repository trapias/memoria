import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
  {
    variants: {
      variant: {
        default:
          "border-transparent bg-primary text-primary-foreground hover:bg-primary/80",
        secondary:
          "border-transparent bg-secondary text-secondary-foreground hover:bg-secondary/80",
        destructive:
          "border-transparent bg-destructive text-destructive-foreground hover:bg-destructive/80",
        outline: "text-foreground",
        causes: "border-transparent bg-red-100 text-red-800",
        fixes: "border-transparent bg-green-100 text-green-800",
        supports: "border-transparent bg-blue-100 text-blue-800",
        opposes: "border-transparent bg-orange-100 text-orange-800",
        follows: "border-transparent bg-purple-100 text-purple-800",
        supersedes: "border-transparent bg-yellow-100 text-yellow-800",
        derives: "border-transparent bg-cyan-100 text-cyan-800",
        part_of: "border-transparent bg-pink-100 text-pink-800",
        related: "border-transparent bg-gray-100 text-gray-800",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}

export { Badge, badgeVariants };
