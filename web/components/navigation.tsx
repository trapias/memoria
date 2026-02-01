"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Brain, GitBranch, Home, Settings } from "lucide-react";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/", label: "Home", icon: Home },
  { href: "/graph", label: "Knowledge Graph", icon: GitBranch },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Navigation() {
  const pathname = usePathname();

  return (
    <nav className="border-b bg-background">
      <div className="container flex h-16 items-center px-4">
        <Link href="/" className="flex items-center gap-2 font-semibold">
          <Brain className="h-6 w-6 text-primary" />
          <span>Memoria</span>
        </Link>

        <div className="ml-8 flex items-center gap-6">
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
      </div>
    </nav>
  );
}
