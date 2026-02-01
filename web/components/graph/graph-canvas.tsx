"use client";

import { useEffect, useRef, useCallback, useMemo, useState, useLayoutEffect } from "react";
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
  const lastClickTime = useRef<number>(0);
  const lastClickedNode = useRef<string | null>(null);
  const DOUBLE_CLICK_DELAY = 300; // ms

  // Track container dimensions for the graph
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });

  useLayoutEffect(() => {
    const updateDimensions = () => {
      if (containerRef.current) {
        const { clientWidth, clientHeight } = containerRef.current;
        if (clientWidth > 0 && clientHeight > 0) {
          setDimensions({ width: clientWidth, height: clientHeight });
        }
      }
    };

    updateDimensions();

    // Use ResizeObserver for responsive updates
    const resizeObserver = new ResizeObserver(updateDimensions);
    if (containerRef.current) {
      resizeObserver.observe(containerRef.current);
    }

    return () => resizeObserver.disconnect();
  }, []);

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

  // Get nodes connected to selected node (for dimming others)
  const selectedConnectedIds = useMemo(() => {
    if (!selectedNode) return null;
    const ids = new Set<string>([selectedNode.id]);
    edges.forEach((e) => {
      if (e.source === selectedNode.id) ids.add(e.target);
      if (e.target === selectedNode.id) ids.add(e.source);
    });
    return ids;
  }, [selectedNode, edges]);

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
    (node: GraphNodeObject, dimmed = false) => {
      let color: string;
      if (selectedNode?.id === node.id) {
        color = "#3b82f6"; // blue for selected
      } else if (node.isCenter) {
        color = "#8b5cf6"; // purple for center
      } else {
        switch (node.type) {
          case "episodic":
            color = "#22c55e"; // green
            break;
          case "semantic":
            color = "#f59e0b"; // amber
            break;
          case "procedural":
            color = "#ec4899"; // pink
            break;
          default:
            color = "#6b7280"; // gray
        }
      }
      // Dim unconnected nodes when a node is selected
      if (dimmed && selectedConnectedIds && !selectedConnectedIds.has(node.id)) {
        return color + "40"; // Add 25% opacity
      }
      return color;
    },
    [selectedNode, selectedConnectedIds]
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

  // Handle click with double-click detection
  const handleClick = useCallback(
    (node: NodeObject | null) => {
      if (!node) return;

      const now = Date.now();
      const graphNode = nodes.find((n) => n.id === node.id);
      if (!graphNode) return;

      // Check for double-click
      if (
        lastClickedNode.current === node.id &&
        now - lastClickTime.current < DOUBLE_CLICK_DELAY
      ) {
        // Double-click: center on node
        onNodeDoubleClick(graphNode);
        lastClickTime.current = 0;
        lastClickedNode.current = null;
      } else {
        // Single click: select node
        onNodeClick(graphNode);
        lastClickTime.current = now;
        lastClickedNode.current = node.id as string;
      }
    },
    [nodes, onNodeClick, onNodeDoubleClick]
  );

  // Custom pointer area for reliable click detection
  // This fixes issues with canvas fingerprinting protection in some browsers
  const paintNodePointerArea = useCallback(
    (node: NodeObject, color: string, ctx: CanvasRenderingContext2D) => {
      const size = getNodeSize(node as GraphNodeObject);
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(node.x ?? 0, node.y ?? 0, size + 2, 0, 2 * Math.PI, false);
      ctx.fill();
    },
    [getNodeSize]
  );

  // Custom node label rendering (added AFTER default node)
  const drawNodeLabel = useCallback(
    (node: NodeObject, ctx: CanvasRenderingContext2D, globalScale: number) => {
      const graphNode = node as GraphNodeObject;
      const size = getNodeSize(graphNode);
      const x = node.x ?? 0;
      const y = node.y ?? 0;

      // Determine if this node should be dimmed
      const isDimmed = selectedConnectedIds && !selectedConnectedIds.has(graphNode.id);

      // Draw label only if zoomed in enough (globalScale > 0.8) or node is selected/center
      const showLabel = globalScale > 0.8 || graphNode.isCenter || selectedNode?.id === graphNode.id;
      if (showLabel && !isDimmed) {
        const label = graphNode.label.length > 25
          ? graphNode.label.substring(0, 22) + "..."
          : graphNode.label;

        const fontSize = Math.max(10 / globalScale, 3);
        ctx.font = `${fontSize}px Inter, sans-serif`;
        ctx.textAlign = "center";
        ctx.textBaseline = "top";

        // Text background for readability
        const textWidth = ctx.measureText(label).width;
        const padding = 2 / globalScale;
        ctx.fillStyle = "rgba(255, 255, 255, 0.85)";
        ctx.fillRect(
          x - textWidth / 2 - padding,
          y + size + 2,
          textWidth + padding * 2,
          fontSize + padding
        );

        // Draw text
        ctx.fillStyle = isDimmed ? "#9ca3af" : "#374151";
        ctx.fillText(label, x, y + size + 3);
      }
    },
    [getNodeSize, selectedNode, selectedConnectedIds]
  );

  return (
    <div ref={containerRef} className="w-full h-full">
      <ForceGraph2D
        ref={fgRef}
        width={dimensions.width}
        height={dimensions.height}
        graphData={graphData}
        nodeLabel={(node) => (node as GraphNodeObject).label}
        nodeColor={(node) => getNodeColor(node as GraphNodeObject, true)}
        nodeVal={(node) => getNodeSize(node as GraphNodeObject)}
        nodeCanvasObjectMode={() => "after"}
        nodeCanvasObject={drawNodeLabel}
        nodePointerAreaPaint={paintNodePointerArea}
        linkColor={(link) => getLinkColor(link as GraphLinkObject)}
        linkWidth={(link) => (link as GraphLinkObject).weight * 2}
        linkDirectionalArrowLength={6}
        linkDirectionalArrowRelPos={1}
        onNodeClick={handleClick}
        linkLabel={(link) => (link as GraphLinkObject).type}
        enableNodeDrag={true}
        enableZoomInteraction={true}
        enablePanInteraction={true}
        backgroundColor="#fafafa"
      />
    </div>
  );
}
