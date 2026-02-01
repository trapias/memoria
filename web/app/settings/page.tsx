"use client";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useStats } from "@/lib/hooks/use-memories";

export default function SettingsPage() {
  const { data: stats } = useStats();

  return (
    <div className="container py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight">Settings</h1>
        <p className="text-muted-foreground">
          Configuration and system information
        </p>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        {/* API Configuration */}
        <Card>
          <CardHeader>
            <CardTitle>API Configuration</CardTitle>
            <CardDescription>
              Current API endpoint configuration
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <p className="text-sm text-muted-foreground">API Base URL</p>
              <code className="text-sm bg-muted px-2 py-1 rounded">
                {process.env.NEXT_PUBLIC_API_URL || "http://localhost:8765"}
              </code>
            </div>
          </CardContent>
        </Card>

        {/* System Stats */}
        <Card>
          <CardHeader>
            <CardTitle>System Statistics</CardTitle>
            <CardDescription>Current database statistics</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-sm text-muted-foreground">Total Memories</p>
                <p className="text-2xl font-bold">
                  {stats?.total_memories ?? 0}
                </p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Total Relations</p>
                <p className="text-2xl font-bold">
                  {stats?.total_relations ?? 0}
                </p>
              </div>
            </div>

            <div>
              <p className="text-sm text-muted-foreground mb-2">By Type</p>
              <div className="flex flex-wrap gap-2">
                {stats?.by_type &&
                  Object.entries(stats.by_type).map(([type, count]) => (
                    <Badge key={type} variant="secondary">
                      {type}: {count}
                    </Badge>
                  ))}
              </div>
            </div>
          </CardContent>
        </Card>

        {/* About */}
        <Card className="md:col-span-2">
          <CardHeader>
            <CardTitle>About Memoria</CardTitle>
            <CardDescription>
              Knowledge Graph Explorer for MCP Memoria
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm">
              Memoria is an MCP (Model Context Protocol) server providing
              persistent, unlimited local AI memory. This web interface allows
              you to explore and manage the knowledge graph of relationships
              between memories.
            </p>

            <div>
              <p className="text-sm text-muted-foreground mb-2">
                Relation Types
              </p>
              <div className="grid grid-cols-3 gap-2 text-sm">
                <div>
                  <Badge variant="causes">causes</Badge> - A leads to B
                </div>
                <div>
                  <Badge variant="fixes">fixes</Badge> - A solves B
                </div>
                <div>
                  <Badge variant="supports">supports</Badge> - A confirms B
                </div>
                <div>
                  <Badge variant="opposes">opposes</Badge> - A contradicts B
                </div>
                <div>
                  <Badge variant="follows">follows</Badge> - A comes after B
                </div>
                <div>
                  <Badge variant="supersedes">supersedes</Badge> - A replaces B
                </div>
                <div>
                  <Badge variant="derives">derives</Badge> - A derived from B
                </div>
                <div>
                  <Badge variant="part_of">part_of</Badge> - A is component of B
                </div>
                <div>
                  <Badge variant="related">related</Badge> - General connection
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
