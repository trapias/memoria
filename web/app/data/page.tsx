"use client";

import { useState } from "react";
import { SessionsTab } from "./sessions-tab";
import { ClientsTab } from "./clients-tab";
import { ProjectsTab } from "./projects-tab";
import { RelationsTab } from "./relations-tab";

const TABS = [
  { id: "sessions", label: "Sessions" },
  { id: "clients", label: "Clients" },
  { id: "projects", label: "Projects" },
  { id: "relations", label: "Relations" },
] as const;

type TabId = (typeof TABS)[number]["id"];

export default function DataPage() {
  const [activeTab, setActiveTab] = useState<TabId>("sessions");

  return (
    <div className="container py-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Data Management</h1>
        <p className="text-muted-foreground">
          View and manage PostgreSQL data: work sessions, clients, projects, and
          memory relations.
        </p>
      </div>

      {/* Tab bar */}
      <div className="border-b">
        <nav className="flex gap-4" role="tablist">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              role="tab"
              aria-selected={activeTab === tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`pb-3 px-1 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab.id
                  ? "border-primary text-primary"
                  : "border-transparent text-muted-foreground hover:text-foreground hover:border-muted-foreground/50"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab content */}
      {activeTab === "sessions" && <SessionsTab />}
      {activeTab === "clients" && <ClientsTab />}
      {activeTab === "projects" && <ProjectsTab />}
      {activeTab === "relations" && <RelationsTab />}
    </div>
  );
}
