"use client";

import ReactMarkdown from "react-markdown";
import { cn } from "@/lib/utils";

interface MarkdownContentProps {
  content: string;
  className?: string;
}

export function MarkdownContent({ content, className }: MarkdownContentProps) {
  return (
    <div
      className={cn(
        "prose prose-sm dark:prose-invert max-w-none",
        // Headings
        "prose-headings:font-semibold prose-headings:mt-4 prose-headings:mb-2",
        "prose-h1:text-xl prose-h2:text-lg prose-h3:text-base",
        // Paragraphs and lists
        "prose-p:my-2 prose-p:leading-relaxed",
        "prose-ul:my-2 prose-ul:pl-4 prose-ol:my-2 prose-ol:pl-4",
        "prose-li:my-0.5",
        // Code
        "prose-code:bg-muted prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-code:text-xs",
        "prose-pre:bg-muted prose-pre:p-3 prose-pre:rounded-md",
        // Links
        "prose-a:text-primary prose-a:no-underline hover:prose-a:underline",
        // Strong/emphasis
        "prose-strong:font-semibold",
        className
      )}
    >
      <ReactMarkdown>{content}</ReactMarkdown>
    </div>
  );
}
