"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Brain, GitBranch, Home, Settings, Sparkles, Database, HardDrive, Table2, Menu, X } from "lucide-react";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/", label: "Home", icon: Home },
  { href: "/memories", label: "Memories", icon: Database },
  { href: "/graph", label: "Graph", icon: GitBranch },
  { href: "/graph/discover", label: "Discover", icon: Sparkles },
  { href: "/data", label: "Data", icon: Table2 },
  { href: "/backup", label: "Backup", icon: HardDrive },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Navigation() {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <nav className="border-b bg-background">
      <div className="container flex h-16 items-center px-4">
        <Link href="/" className="flex items-center gap-2 font-semibold">
          <Brain className="h-6 w-6 text-primary" />
          <span>Memoria</span>
        </Link>

        {/* Desktop nav — visible from lg (1024px+) */}
        <div className="ml-8 hidden lg:flex items-center gap-6">
          {navItems.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-2 text-sm font-medium transition-colors hover:text-primary",
                pathname === item.href
                  ? "text-primary"
                  : "text-muted-foreground"
              )}
            >
              <item.icon className="h-4 w-4" />
              {item.label}
            </Link>
          ))}
        </div>

        {/* Mobile hamburger button */}
        <button
          className="ml-auto lg:hidden p-2 text-muted-foreground hover:text-foreground transition-colors"
          onClick={() => setMobileOpen((v) => !v)}
          aria-label={mobileOpen ? "Close menu" : "Open menu"}
        >
          {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </div>

      {/* Mobile nav panel */}
      {mobileOpen && (
        <div className="lg:hidden border-t bg-background px-4 pb-4 pt-2">
          <div className="flex flex-col gap-1">
            {navItems.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setMobileOpen(false)}
                className={cn(
                  "flex items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium transition-colors hover:bg-muted",
                  pathname === item.href
                    ? "text-primary bg-primary/5"
                    : "text-muted-foreground"
                )}
              >
                <item.icon className="h-4 w-4" />
                {item.label}
              </Link>
            ))}
          </div>
        </div>
      )}
    </nav>
  );
}
