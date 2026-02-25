"use client";

import { useState, useCallback } from "react";
import {
  useSessionList,
  useSessionSummary,
  useCreateSession,
  useUpdateSession,
  useDeleteSession,
  useClientList,
  useProjectList,
  SESSION_CATEGORIES,
  CATEGORY_COLORS,
  formatDuration,
  formatDate,
  formatDateTime,
} from "@/lib/hooks/use-data";
import { api, type WorkSessionResponse } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import {
  Pencil,
  Trash2,
  Plus,
  Download,
  Clock,
  BarChart3,
  Users,
  Loader2,
} from "lucide-react";
import { SortableHeader, type SortDir } from "@/components/ui/sortable-header";

// ─── Helpers ──────────────────────────────────────────────────────────────────

const STATUS_COLORS: Record<string, string> = {
  active: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
  paused:
    "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200",
  completed:
    "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200",
};

function toDatetimeLocal(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  const pad = (n: number) => n.toString().padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function fromDatetimeLocal(value: string): string {
  if (!value) return "";
  return new Date(value).toISOString();
}

function truncate(text: string, maxLen: number): string {
  if (!text) return "";
  if (text.length <= maxLen) return text;
  return text.slice(0, maxLen) + "...";
}

const PAGE_SIZE = 15;

// ─── Form State ───────────────────────────────────────────────────────────────

interface SessionFormData {
  description: string;
  category: string;
  client_id: string;
  project_id: string;
  start_time: string;
  end_time: string;
  issue_number: string;
  pr_number: string;
  branch: string;
  notes: string;
}

const EMPTY_FORM: SessionFormData = {
  description: "",
  category: "coding",
  client_id: "",
  project_id: "",
  start_time: "",
  end_time: "",
  issue_number: "",
  pr_number: "",
  branch: "",
  notes: "",
};

function sessionToForm(s: WorkSessionResponse): SessionFormData {
  return {
    description: s.description,
    category: s.category,
    client_id: s.client_id || "",
    project_id: s.project_id || "",
    start_time: toDatetimeLocal(s.start_time),
    end_time: toDatetimeLocal(s.end_time),
    issue_number: s.issue_number != null ? String(s.issue_number) : "",
    pr_number: s.pr_number != null ? String(s.pr_number) : "",
    branch: s.branch || "",
    notes: (s.notes || []).join("\n"),
  };
}

// ─── Component ────────────────────────────────────────────────────────────────

export function SessionsTab() {
  // Filters
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [category, setCategory] = useState("");
  const [status, setStatus] = useState("");
  const [filterClientId, setFilterClientId] = useState("");
  const [filterProjectId, setFilterProjectId] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [sortBy, setSortBy] = useState("start_time");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  // Dialog
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingSession, setEditingSession] =
    useState<WorkSessionResponse | null>(null);
  const [form, setForm] = useState<SessionFormData>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);

  // Queries
  const summaryQuery = useSessionSummary({
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
  });

  const listQuery = useSessionList({
    page,
    page_size: PAGE_SIZE,
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
    client_id: filterClientId || undefined,
    project_id: filterProjectId || undefined,
    category: category || undefined,
    status: status || undefined,
    search: search || undefined,
    sort_by: sortBy,
    sort_dir: sortDir,
  });

  const clientsQuery = useClientList();
  const allProjectsQuery = useProjectList();
  const [selectedClientId, setSelectedClientId] = useState<string | undefined>(
    undefined
  );
  const projectsQuery = useProjectList(selectedClientId);

  // Mutations
  const createMutation = useCreateSession();
  const updateMutation = useUpdateSession();
  const deleteMutation = useDeleteSession();

  const summary = summaryQuery.data;
  const sessions = listQuery.data?.items ?? [];
  const totalSessions = listQuery.data?.total ?? 0;
  const totalPages = listQuery.data?.pages ?? 1;

  // ─── Handlers ─────────────────────────────────────────────────────────────

  const openCreate = useCallback(() => {
    setEditingSession(null);
    setForm(EMPTY_FORM);
    setSelectedClientId(undefined);
    setDialogOpen(true);
  }, []);

  const openEdit = useCallback((session: WorkSessionResponse) => {
    setEditingSession(session);
    setForm(sessionToForm(session));
    setSelectedClientId(session.client_id || undefined);
    setDialogOpen(true);
  }, []);

  const handleSave = useCallback(async () => {
    setSaving(true);
    try {
      const notes = form.notes
        .split("\n")
        .map((l) => l.trim())
        .filter(Boolean);

      const body = {
        description: form.description,
        category: form.category || undefined,
        client_id: form.client_id || undefined,
        project_id: form.project_id || undefined,
        start_time: form.start_time ? fromDatetimeLocal(form.start_time) : undefined,
        end_time: form.end_time ? fromDatetimeLocal(form.end_time) : undefined,
        issue_number: form.issue_number ? Number(form.issue_number) : undefined,
        pr_number: form.pr_number ? Number(form.pr_number) : undefined,
        branch: form.branch || undefined,
        notes: notes.length > 0 ? notes : undefined,
      };

      if (editingSession) {
        await updateMutation.mutateAsync({ id: editingSession.id, body });
      } else {
        await createMutation.mutateAsync({
          ...body,
          description: body.description || "Untitled session",
          start_time: body.start_time || new Date().toISOString(),
          end_time: body.end_time || new Date().toISOString(),
        });
      }
      setDialogOpen(false);
    } finally {
      setSaving(false);
    }
  }, [form, editingSession, createMutation, updateMutation]);

  const handleDelete = useCallback(
    async (session: WorkSessionResponse) => {
      const confirmed = window.confirm(
        `Delete session "${truncate(session.description, 50)}"? This action cannot be undone.`
      );
      if (!confirmed) return;
      await deleteMutation.mutateAsync(session.id);
    },
    [deleteMutation]
  );

  const handleExportCsv = useCallback(async () => {
    try {
      const blob = await api.exportSessionsCsv({
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `sessions-${new Date().toISOString().split("T")[0]}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error("CSV export failed:", err);
    }
  }, [dateFrom, dateTo]);

  const updateField = useCallback(
    <K extends keyof SessionFormData>(key: K, value: SessionFormData[K]) => {
      setForm((prev) => ({ ...prev, [key]: value }));
      if (key === "client_id") {
        setSelectedClientId(value as string || undefined);
        setForm((prev) => ({ ...prev, project_id: "" }));
      }
    },
    []
  );

  // ─── Render ───────────────────────────────────────────────────────────────

  return (
    <div className="space-y-6">
      {/* Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Total Hours
            </CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {summary ? formatDuration(summary.total_minutes) : "--"}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Sessions
            </CardTitle>
            <BarChart3 className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {summary?.session_count ?? "--"}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Avg Duration
            </CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {summary ? formatDuration(Math.round(summary.avg_minutes)) : "--"}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Active Clients
            </CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {summary?.client_count ?? "--"}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Filters Bar */}
      <div className="flex flex-wrap items-end gap-3">
        <div className="space-y-1">
          <Label className="text-xs text-muted-foreground">From</Label>
          <Input
            type="date"
            value={dateFrom}
            onChange={(e) => {
              setDateFrom(e.target.value);
              setPage(1);
            }}
            className="w-[150px]"
          />
        </div>

        <div className="space-y-1">
          <Label className="text-xs text-muted-foreground">To</Label>
          <Input
            type="date"
            value={dateTo}
            onChange={(e) => {
              setDateTo(e.target.value);
              setPage(1);
            }}
            className="w-[150px]"
          />
        </div>

        <div className="space-y-1">
          <Label className="text-xs text-muted-foreground">Category</Label>
          <Select
            value={category}
            onValueChange={(v) => {
              setCategory(v === "all" ? "" : v);
              setPage(1);
            }}
          >
            <SelectTrigger className="w-[150px]">
              <SelectValue placeholder="All categories" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All categories</SelectItem>
              {SESSION_CATEGORIES.map((cat) => (
                <SelectItem key={cat} value={cat}>
                  {cat.charAt(0).toUpperCase() + cat.slice(1)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-1">
          <Label className="text-xs text-muted-foreground">Client</Label>
          <Select
            value={filterClientId || "all"}
            onValueChange={(v) => {
              setFilterClientId(v === "all" ? "" : v);
              setFilterProjectId("");
              setPage(1);
            }}
          >
            <SelectTrigger className="w-[150px]">
              <SelectValue placeholder="All clients" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All clients</SelectItem>
              {[...(clientsQuery.data ?? [])].sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: "base" })).map((c) => (
                <SelectItem key={c.id} value={c.id}>
                  {c.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-1">
          <Label className="text-xs text-muted-foreground">Project</Label>
          <Select
            value={filterProjectId || "all"}
            onValueChange={(v) => {
              setFilterProjectId(v === "all" ? "" : v);
              setPage(1);
            }}
          >
            <SelectTrigger className="w-[150px]">
              <SelectValue placeholder="All projects" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All projects</SelectItem>
              {[...(filterClientId
                ? (allProjectsQuery.data ?? []).filter(
                    (p) => p.client_id === filterClientId
                  )
                : (allProjectsQuery.data ?? [])
              )].sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: "base" })).map((p) => (
                <SelectItem key={p.id} value={p.id}>
                  {p.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-1">
          <Label className="text-xs text-muted-foreground">Status</Label>
          <Select
            value={status}
            onValueChange={(v) => {
              setStatus(v === "all" ? "" : v);
              setPage(1);
            }}
          >
            <SelectTrigger className="w-[140px]">
              <SelectValue placeholder="All statuses" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All statuses</SelectItem>
              <SelectItem value="active">Active</SelectItem>
              <SelectItem value="paused">Paused</SelectItem>
              <SelectItem value="completed">Completed</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-1">
          <Label className="text-xs text-muted-foreground">Search</Label>
          <Input
            placeholder="Search description..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            className="w-[200px]"
          />
        </div>

        <div className="flex gap-2 ml-auto">
          <Button variant="outline" size="sm" onClick={handleExportCsv}>
            <Download className="h-4 w-4 mr-1" />
            CSV
          </Button>
          <Button size="sm" onClick={openCreate}>
            <Plus className="h-4 w-4 mr-1" />
            New
          </Button>
        </div>
      </div>

      {/* Table */}
      <div className="rounded-md border">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-muted/50">
              <SortableHeader label="Date" field="start_time" currentField={sortBy} currentDir={sortDir} onSort={(f, d) => { setSortBy(f); setSortDir(d); setPage(1); }} className="text-left text-muted-foreground" />
              <th className="px-4 py-3 text-left font-medium text-muted-foreground">
                Description
              </th>
              <SortableHeader label="Duration" field="duration_minutes" currentField={sortBy} currentDir={sortDir} onSort={(f, d) => { setSortBy(f); setSortDir(d); setPage(1); }} className="text-left text-muted-foreground" />
              <SortableHeader label="Category" field="category" currentField={sortBy} currentDir={sortDir} onSort={(f, d) => { setSortBy(f); setSortDir(d); setPage(1); }} className="text-left text-muted-foreground" />
              <SortableHeader label="Client" field="client_name" currentField={sortBy} currentDir={sortDir} onSort={(f, d) => { setSortBy(f); setSortDir(d); setPage(1); }} className="text-left text-muted-foreground" />
              <SortableHeader label="Project" field="project_name" currentField={sortBy} currentDir={sortDir} onSort={(f, d) => { setSortBy(f); setSortDir(d); setPage(1); }} className="text-left text-muted-foreground" />
              <SortableHeader label="Status" field="status" currentField={sortBy} currentDir={sortDir} onSort={(f, d) => { setSortBy(f); setSortDir(d); setPage(1); }} className="text-left text-muted-foreground" />
              <th className="px-4 py-3 text-right font-medium text-muted-foreground">
                Actions
              </th>
            </tr>
          </thead>
          <tbody>
            {listQuery.isLoading ? (
              <tr>
                <td colSpan={8} className="px-4 py-12 text-center">
                  <Loader2 className="h-5 w-5 animate-spin mx-auto text-muted-foreground" />
                </td>
              </tr>
            ) : sessions.length === 0 ? (
              <tr>
                <td
                  colSpan={8}
                  className="px-4 py-12 text-center text-muted-foreground"
                >
                  No sessions found.
                </td>
              </tr>
            ) : (
              sessions.map((session) => (
                <tr
                  key={session.id}
                  className="border-b last:border-0 hover:bg-muted/30 transition-colors"
                >
                  <td className="px-4 py-3 whitespace-nowrap">
                    {formatDate(session.start_time)}
                  </td>
                  <td
                    className="px-4 py-3 max-w-[250px] truncate"
                    title={session.description}
                  >
                    {truncate(session.description, 60)}
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap">
                    {formatDuration(session.duration_minutes)}
                  </td>
                  <td className="px-4 py-3">
                    <Badge
                      variant="secondary"
                      className={
                        CATEGORY_COLORS[session.category] || CATEGORY_COLORS.other
                      }
                    >
                      {session.category}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {session.client_name || "--"}
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {session.project_name || "--"}
                  </td>
                  <td className="px-4 py-3">
                    <Badge
                      variant="secondary"
                      className={
                        STATUS_COLORS[session.status] || STATUS_COLORS.completed
                      }
                    >
                      {session.status}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex justify-end gap-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8"
                        onClick={() => openEdit(session)}
                        title="Edit session"
                      >
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 text-destructive hover:text-destructive"
                        onClick={() => handleDelete(session)}
                        title="Delete session"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between">
        <span className="text-sm text-muted-foreground">
          {totalSessions} session{totalSessions !== 1 ? "s" : ""}
        </span>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={page <= 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
          >
            Previous
          </Button>
          <span className="text-sm text-muted-foreground">
            Page {page} of {totalPages}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= totalPages}
            onClick={() => setPage((p) => p + 1)}
          >
            Next
          </Button>
        </div>
      </div>

      {/* Edit / Create Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              {editingSession ? "Edit Session" : "New Session"}
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-4 py-2">
            {/* Description */}
            <div className="space-y-2">
              <Label htmlFor="sess-description">Description</Label>
              <Input
                id="sess-description"
                value={form.description}
                onChange={(e) => updateField("description", e.target.value)}
                placeholder="What did you work on?"
              />
            </div>

            {/* Category */}
            <div className="space-y-2">
              <Label htmlFor="sess-category">Category</Label>
              <Select
                value={form.category}
                onValueChange={(v) => updateField("category", v)}
              >
                <SelectTrigger id="sess-category">
                  <SelectValue placeholder="Select category" />
                </SelectTrigger>
                <SelectContent>
                  {SESSION_CATEGORIES.map((cat) => (
                    <SelectItem key={cat} value={cat}>
                      {cat.charAt(0).toUpperCase() + cat.slice(1)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Client */}
            <div className="space-y-2">
              <Label htmlFor="sess-client">Client</Label>
              <Select
                value={form.client_id || "none"}
                onValueChange={(v) =>
                  updateField("client_id", v === "none" ? "" : v)
                }
              >
                <SelectTrigger id="sess-client">
                  <SelectValue placeholder="No client" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">No client</SelectItem>
                  {[...(clientsQuery.data ?? [])].sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: "base" })).map((c) => (
                    <SelectItem key={c.id} value={c.id}>
                      {c.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Project */}
            <div className="space-y-2">
              <Label htmlFor="sess-project">Project</Label>
              <Select
                value={form.project_id || "none"}
                onValueChange={(v) =>
                  updateField("project_id", v === "none" ? "" : v)
                }
              >
                <SelectTrigger id="sess-project">
                  <SelectValue placeholder="No project" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">No project</SelectItem>
                  {[...(projectsQuery.data ?? [])].sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: "base" })).map((p) => (
                    <SelectItem key={p.id} value={p.id}>
                      {p.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Start / End time */}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="sess-start">Start Time</Label>
                <Input
                  id="sess-start"
                  type="datetime-local"
                  value={form.start_time}
                  onChange={(e) => updateField("start_time", e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="sess-end">End Time</Label>
                <Input
                  id="sess-end"
                  type="datetime-local"
                  value={form.end_time}
                  onChange={(e) => updateField("end_time", e.target.value)}
                />
              </div>
            </div>

            {/* Issue / PR / Branch */}
            <div className="grid grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label htmlFor="sess-issue">Issue #</Label>
                <Input
                  id="sess-issue"
                  type="number"
                  value={form.issue_number}
                  onChange={(e) => updateField("issue_number", e.target.value)}
                  placeholder="Optional"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="sess-pr">PR #</Label>
                <Input
                  id="sess-pr"
                  type="number"
                  value={form.pr_number}
                  onChange={(e) => updateField("pr_number", e.target.value)}
                  placeholder="Optional"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="sess-branch">Branch</Label>
                <Input
                  id="sess-branch"
                  value={form.branch}
                  onChange={(e) => updateField("branch", e.target.value)}
                  placeholder="Optional"
                />
              </div>
            </div>

            {/* Notes */}
            <div className="space-y-2">
              <Label htmlFor="sess-notes">Notes (one per line)</Label>
              <Textarea
                id="sess-notes"
                value={form.notes}
                onChange={(e) => updateField("notes", e.target.value)}
                placeholder="Add notes, one per line..."
                rows={3}
              />
            </div>
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDialogOpen(false)}
              disabled={saving}
            >
              Cancel
            </Button>
            <Button onClick={handleSave} disabled={saving}>
              {saving && <Loader2 className="h-4 w-4 mr-1 animate-spin" />}
              {editingSession ? "Save Changes" : "Create Session"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
