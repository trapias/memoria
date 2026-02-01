"use client";

import { useStats } from "@/lib/hooks/use-memories";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Brain, GitBranch, Database, Plus } from "lucide-react";
import Link from "next/link";

export default function DashboardPage() {
  const { data: stats, isLoading } = useStats();

  return (
    <div className="container py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
        <p className="text-muted-foreground">
          Welcome to Memoria - your knowledge graph explorer
        </p>
      </div>

      {/* Quick Stats */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4 mb-8">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">
              Total Memories
            </CardTitle>
            <Brain className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {isLoading ? "..." : stats?.total_memories ?? 0}
            </div>
            <p className="text-xs text-muted-foreground">
              Across all collections
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Relations</CardTitle>
            <GitBranch className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {isLoading ? "..." : stats?.total_relations ?? 0}
            </div>
            <p className="text-xs text-muted-foreground">
              Knowledge graph connections
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Episodic</CardTitle>
            <Database className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {isLoading ? "..." : stats?.by_type?.episodic ?? 0}
            </div>
            <p className="text-xs text-muted-foreground">
              Events & conversations
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Semantic</CardTitle>
            <Database className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {isLoading ? "..." : stats?.by_type?.semantic ?? 0}
            </div>
            <p className="text-xs text-muted-foreground">Facts & knowledge</p>
          </CardContent>
        </Card>
      </div>

      {/* Quick Actions */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>Explore Knowledge Graph</CardTitle>
            <CardDescription>
              Visualize relationships between memories
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Link href="/graph">
              <Button className="w-full">
                <GitBranch className="mr-2 h-4 w-4" />
                Open Graph Explorer
              </Button>
            </Link>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Memory Types</CardTitle>
            <CardDescription>Browse memories by type</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            <div className="flex justify-between text-sm">
              <span>Episodic</span>
              <span className="font-medium">
                {stats?.by_type?.episodic ?? 0}
              </span>
            </div>
            <div className="flex justify-between text-sm">
              <span>Semantic</span>
              <span className="font-medium">
                {stats?.by_type?.semantic ?? 0}
              </span>
            </div>
            <div className="flex justify-between text-sm">
              <span>Procedural</span>
              <span className="font-medium">
                {stats?.by_type?.procedural ?? 0}
              </span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Quick Search</CardTitle>
            <CardDescription>
              Search memories semantically
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Link href="/graph">
              <Button variant="outline" className="w-full">
                <Plus className="mr-2 h-4 w-4" />
                Search & Explore
              </Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
