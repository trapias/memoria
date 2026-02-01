"use client";

import { useState, useCallback } from "react";
import Link from "next/link";
import { Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { GraphCanvas } from "@/components/graph/graph-canvas";
import { GraphControls } from "@/components/graph/graph-controls";
import { GraphSidebar } from "@/components/graph/graph-sidebar";
import { MemorySearch } from "@/components/graph/memory-search";
import { SuggestionsPanel } from "@/components/graph/suggestions-panel";
import { useSubgraph } from "@/lib/hooks/use-graph";
import { GraphNode } from "@/lib/api";

export default function GraphPage() {
  const [centerId, setCenterId] = useState<string | null>(null);
  const [depth, setDepth] = useState(2);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [relationFilter, setRelationFilter] = useState<string | null>(null);

  const { data: subgraph, isLoading } = useSubgraph(centerId, depth);

  const handleNodeSelect = useCallback((node: GraphNode | null) => {
    setSelectedNode(node);
  }, []);

  const handleMemorySelect = useCallback((memoryId: string) => {
    setCenterId(memoryId);
    setSelectedNode(null);
  }, []);

  const handleNodeClick = useCallback((node: GraphNode) => {
    setSelectedNode(node);
  }, []);

  const handleNodeDoubleClick = useCallback((node: GraphNode) => {
    setCenterId(node.id);
    setSelectedNode(node);
  }, []);

  return (
    <div className="flex h-[calc(100vh-64px)]">
      {/* Main Content */}
      <div className="flex-1 flex flex-col">
        {/* Controls */}
        <div className="border-b p-4 bg-background">
          <div className="flex items-center gap-4">
            <div className="flex-1 max-w-md">
              <MemorySearch onSelect={handleMemorySelect} />
            </div>
            <GraphControls
              depth={depth}
              onDepthChange={setDepth}
              relationFilter={relationFilter}
              onRelationFilterChange={setRelationFilter}
            />
            <Link href="/graph/discover">
              <Button variant="outline" size="sm">
                <Sparkles className="h-4 w-4 mr-2" />
                Discover Relations
              </Button>
            </Link>
          </div>
        </div>

        {/* Graph Canvas */}
        <div className="flex-1 relative">
          {!centerId ? (
            <div className="absolute inset-0 flex items-center justify-center text-muted-foreground">
              <div className="text-center">
                <p className="text-lg mb-2">Search for a memory to explore</p>
                <p className="text-sm">
                  Use the search bar above to find a memory and visualize its relationships
                </p>
              </div>
            </div>
          ) : isLoading ? (
            <div className="absolute inset-0 flex items-center justify-center">
              <p className="text-muted-foreground">Loading graph...</p>
            </div>
          ) : (
            <GraphCanvas
              nodes={subgraph?.nodes ?? []}
              edges={subgraph?.edges ?? []}
              selectedNode={selectedNode}
              onNodeClick={handleNodeClick}
              onNodeDoubleClick={handleNodeDoubleClick}
              relationFilter={relationFilter}
            />
          )}
        </div>
      </div>

      {/* Sidebar */}
      <div className="w-80 border-l bg-background flex flex-col">
        <GraphSidebar
          selectedNode={selectedNode}
          onNodeSelect={handleNodeSelect}
          onCenterNode={handleMemorySelect}
        />

        {selectedNode && (
          <SuggestionsPanel
            memoryId={selectedNode.id}
            onAccept={() => {
              // Refresh will happen via query invalidation
            }}
          />
        )}
      </div>
    </div>
  );
}
