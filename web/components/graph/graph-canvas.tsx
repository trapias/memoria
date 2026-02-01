"use client";

import { useEffect, useRef, useCallback, useMemo } from "react";
import dynamic from "next/dynamic";
import type { ForceGraphMethods, NodeObject, LinkObject } from "react-force-graph-2d";
import { GraphNode, GraphEdge } from "@/lib/api";
import { RELATION_COLORS } from "@/lib/hooks/use-graph";

// Dynamic import to avoid SSR issues with react-force-graph
const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), {
  ssr: false,
  loading: () => (
    <div className="w-full h-full flex items-center justify-center">
      <p className="text-muted-foreground">Loading graph...</p>
    </div>
  ),
});

interface GraphCanvasProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  selectedNode: GraphNode | null;
  onNodeClick: (node: GraphNode) => void;
  onNodeDoubleClick: (node: GraphNode) => void;
  relationFilter: string | null;
}

interface GraphNodeObject extends NodeObject {
  id: string;
  label: string;
  type: string | null;
  importance: number;
  isCenter: boolean;
  depth?: number;
}

interface GraphLinkObject extends LinkObject {
  source: string | GraphNodeObject;
  target: string | GraphNodeObject;
  type: string;
  weight: number;
}

export function GraphCanvas({
  nodes,
  edges,
  selectedNode,
  onNodeClick,
  onNodeDoubleClick,
  relationFilter,
}: GraphCanvasProps) {
  const fgRef = useRef<ForceGraphMethods>();
  const containerRef = useRef<HTMLDivElement>(null);

  // Filter edges by relation type if filter is set
  const filteredEdges = useMemo(() => {
    if (!relationFilter) return edges;
    return edges.filter((e) => e.type === relationFilter);
  }, [edges, relationFilter]);

  // Get node IDs that are connected by filtered edges
  const connectedNodeIds = useMemo(() => {
    const ids = new Set<string>();
    filteredEdges.forEach((e) => {
      ids.add(e.source);
      ids.add(e.target);
    });
    return ids;
  }, [filteredEdges]);

  // Filter nodes to only show connected ones when filter is active
  const filteredNodes = useMemo(() => {
    if (!relationFilter) return nodes;
    return nodes.filter((n) => connectedNodeIds.has(n.id) || n.isCenter);
  }, [nodes, relationFilter, connectedNodeIds]);

  // Convert to graph data format
  const graphData = useMemo(
    () => ({
      nodes: filteredNodes.map((n) => ({
        id: n.id,
        label: n.label,
        type: n.type,
        importance: n.importance,
        isCenter: n.isCenter,
        depth: n.depth,
      })),
      links: filteredEdges.map((e) => ({
        source: e.source,
        target: e.target,
        type: e.type,
        weight: e.weight,
      })),
    }),
    [filteredNodes, filteredEdges]
  );

  // Center graph on load
  useEffect(() => {
    if (fgRef.current && graphData.nodes.length > 0) {
      setTimeout(() => {
        fgRef.current?.zoomToFit(400, 50);
      }, 500);
    }
  }, [graphData.nodes.length]);

  // Node colors based on type
  const getNodeColor = useCallback(
    (node: GraphNodeObject) => {
      if (selectedNode?.id === node.id) {
        return "#3b82f6"; // blue for selected
      }
      if (node.isCenter) {
        return "#8b5cf6"; // purple for center
      }
      switch (node.type) {
        case "episodic":
          return "#22c55e"; // green
        case "semantic":
          return "#f59e0b"; // amber
        case "procedural":
          return "#ec4899"; // pink
        default:
          return "#6b7280"; // gray
      }
    },
    [selectedNode]
  );

  // Node size based on importance
  const getNodeSize = useCallback((node: GraphNodeObject) => {
    const baseSize = 6;
    const importanceBonus = node.importance * 6;
    const centerBonus = node.isCenter ? 4 : 0;
    return baseSize + importanceBonus + centerBonus;
  }, []);

  // Link color based on relation type
  const getLinkColor = useCallback((link: GraphLinkObject) => {
    return RELATION_COLORS[link.type] ?? "#6b7280";
  }, []);

  // Handle click
  const handleClick = useCallback(
    (node: NodeObject | null) => {
      if (node) {
        const graphNode = nodes.find((n) => n.id === node.id);
        if (graphNode) {
          onNodeClick(graphNode);
        }
      }
    },
    [nodes, onNodeClick]
  );

  // Handle double click
  const handleDoubleClick = useCallback(
    (node: NodeObject | null) => {
      if (node) {
        const graphNode = nodes.find((n) => n.id === node.id);
        if (graphNode) {
          onNodeDoubleClick(graphNode);
        }
      }
    },
    [nodes, onNodeDoubleClick]
  );

  return (
    <div ref={containerRef} className="w-full h-full">
      <ForceGraph2D
        ref={fgRef}
        graphData={graphData}
        nodeLabel={(node) => (node as GraphNodeObject).label}
        nodeColor={(node) => getNodeColor(node as GraphNodeObject)}
        nodeVal={(node) => getNodeSize(node as GraphNodeObject)}
        linkColor={(link) => getLinkColor(link as GraphLinkObject)}
        linkWidth={(link) => (link as GraphLinkObject).weight * 2}
        linkDirectionalArrowLength={6}
        linkDirectionalArrowRelPos={1}
        onNodeClick={handleClick}
        onNodeRightClick={handleDoubleClick}
        linkLabel={(link) => (link as GraphLinkObject).type}
        enableNodeDrag={true}
        enableZoomInteraction={true}
        enablePanInteraction={true}
        backgroundColor="#fafafa"
      />
    </div>
  );
}
