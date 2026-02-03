"use client";

import { useState, useCallback, useEffect, Suspense, useRef } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { Sparkles, Network, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { GraphCanvas } from "@/components/graph/graph-canvas";
import { GraphControls } from "@/components/graph/graph-controls";
import { GraphSidebar } from "@/components/graph/graph-sidebar";
import { MemorySearch } from "@/components/graph/memory-search";
import { SuggestionsPanel } from "@/components/graph/suggestions-panel";
import { RelationForm } from "@/components/graph/relation-form";
import { useSubgraph, useGraphOverview } from "@/lib/hooks/use-graph";
import { GraphNode } from "@/lib/api";

// Inner component that uses useSearchParams
function GraphPageInner() {
  const searchParams = useSearchParams();
  const centerFromUrl = searchParams.get("center");

  const [centerId, setCenterId] = useState<string | null>(centerFromUrl);
  const [depth, setDepth] = useState(2);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [relationFilter, setRelationFilter] = useState<string | null>(null);
  const [showOverview, setShowOverview] = useState(false);
  const [showRelationForm, setShowRelationForm] = useState(false);

  // Update centerId when URL changes
  useEffect(() => {
    if (centerFromUrl && centerFromUrl !== centerId) {
      setCenterId(centerFromUrl);
    }
  }, [centerFromUrl]);

  const { data: subgraph, isLoading } = useSubgraph(centerId, depth);
  const { data: overviewGraph, isLoading: isLoadingOverview } = useGraphOverview(
    showOverview && !centerId,
    10,
    2
  );

  // Track the last auto-selected centerId to avoid re-selecting on every render
  const lastAutoSelectedRef = useRef<string | null>(null);

  // Auto-select the center node when subgraph loads (for search selection and URL navigation)
  useEffect(() => {
    if (centerId && subgraph && subgraph.nodes.length > 0 && lastAutoSelectedRef.current !== centerId) {
      const centerNode = subgraph.nodes.find(n => n.id === centerId);
      if (centerNode) {
        lastAutoSelectedRef.current = centerId;
        setSelectedNode(centerNode);
      }
    }
  }, [centerId, subgraph]);

  const handleNodeSelect = useCallback((node: GraphNode | null) => {
    setSelectedNode(node);
  }, []);

  const handleMemorySelect = useCallback((memoryId: string) => {
    lastAutoSelectedRef.current = null; // Reset so new center gets auto-selected
    setCenterId(memoryId);
    setShowOverview(false);
    setSelectedNode(null);
  }, []);

  const handleShowOverview = useCallback(() => {
    lastAutoSelectedRef.current = null;
    setCenterId(null);
    setShowOverview(true);
    setSelectedNode(null);
  }, []);

  const handleAddRelationFromNode = useCallback(() => {
    if (selectedNode) {
      setShowRelationForm(true);
    }
  }, [selectedNode]);

  // Determine which graph data to display
  const activeGraph = centerId ? subgraph : showOverview ? overviewGraph : null;
  const isGraphLoading = centerId ? isLoading : isLoadingOverview;
  const hasNoRelations = showOverview && overviewGraph && overviewGraph.nodes.length === 0;

  const handleNodeClick = useCallback((node: GraphNode) => {
    setSelectedNode(node);
  }, []);

  const handleNodeDoubleClick = useCallback((node: GraphNode) => {
    setCenterId(node.id);
    setSelectedNode(node);
  }, []);

  return (
    <div className="flex h-[calc(100vh-64px)] overflow-hidden">
      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Controls */}
        <div className="border-b p-4 bg-background">
          <div className="flex items-center gap-4">
            <div className="flex-1 max-w-md">
              <MemorySearch onSelect={handleMemorySelect} />
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={handleShowOverview}
              disabled={isLoadingOverview}
            >
              <Network className="h-4 w-4 mr-2" />
              Show Overview
            </Button>
            <GraphControls
              depth={depth}
              onDepthChange={setDepth}
              relationFilter={relationFilter}
              onRelationFilterChange={setRelationFilter}
            />
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowRelationForm(true)}
              disabled={!selectedNode}
              title={selectedNode ? "Add relation from selected node" : "Select a node first"}
            >
              <Plus className="h-4 w-4 mr-2" />
              Add Relation
            </Button>
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
          {!centerId && !showOverview ? (
            <div className="absolute inset-0 flex items-center justify-center text-muted-foreground">
              <div className="text-center">
                <p className="text-lg mb-2">Search for a memory to explore</p>
                <p className="text-sm mb-4">
                  Use the search bar above to find a memory and visualize its relationships
                </p>
                <p className="text-sm">
                  Or click <strong>Show Overview</strong> to see your most connected memories
                </p>
              </div>
            </div>
          ) : isGraphLoading ? (
            <div className="absolute inset-0 flex items-center justify-center">
              <p className="text-muted-foreground">Loading graph...</p>
            </div>
          ) : hasNoRelations ? (
            <div className="absolute inset-0 flex items-center justify-center text-muted-foreground">
              <div className="text-center">
                <p className="text-lg mb-2">No relations yet</p>
                <p className="text-sm mb-4">
                  Your knowledge graph is empty. Use{" "}
                  <Link href="/graph/discover" className="text-primary hover:underline">
                    Discover Relations
                  </Link>{" "}
                  to find and create connections between your memories.
                </p>
              </div>
            </div>
          ) : (
            <GraphCanvas
              nodes={activeGraph?.nodes ?? []}
              edges={activeGraph?.edges ?? []}
              selectedNode={selectedNode}
              onNodeClick={handleNodeClick}
              onNodeDoubleClick={handleNodeDoubleClick}
              relationFilter={relationFilter}
              isOverview={showOverview && !centerId}
            />
          )}
        </div>
      </div>

      {/* Sidebar */}
      <div className="w-80 shrink-0 border-l bg-background flex flex-col overflow-y-auto">
        <GraphSidebar
          selectedNode={selectedNode}
          allNodes={activeGraph?.nodes ?? []}
          onNodeSelect={handleNodeSelect}
          onCenterNode={handleMemorySelect}
          onAddRelation={handleAddRelationFromNode}
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

      {/* Relation Form Dialog */}
      {selectedNode && (
        <RelationForm
          sourceId={selectedNode.id}
          sourceLabel={selectedNode.label}
          open={showRelationForm}
          onOpenChange={setShowRelationForm}
          onSuccess={() => {
            // Refresh will happen via query invalidation
          }}
        />
      )}
    </div>
  );
}

// Main export with Suspense boundary for useSearchParams
export default function GraphPage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-[calc(100vh-64px)] items-center justify-center">
          <p className="text-muted-foreground">Loading...</p>
        </div>
      }
    >
      <GraphPageInner />
    </Suspense>
  );
}
