"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
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
import { Pencil, Trash2, Plus, Loader2, ExternalLink } from "lucide-react";
import { type DataProject } from "@/lib/api";
import {
  useProjectList,
  useClientList,
  useCreateProject,
  useUpdateProject,
  useDeleteProject,
  formatDuration,
  formatDate,
} from "@/lib/hooks/use-data";

interface ProjectFormData {
  name: string;
  client_id: string;
  repo: string;
}

const EMPTY_FORM: ProjectFormData = {
  name: "",
  client_id: "",
  repo: "",
};

export function ProjectsTab() {
  const [selectedClientId, setSelectedClientId] = useState<string | undefined>(
    undefined
  );
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingProject, setEditingProject] = useState<DataProject | null>(
    null
  );
  const [form, setForm] = useState<ProjectFormData>(EMPTY_FORM);

  const { data: projects, isLoading } = useProjectList(selectedClientId);
  const { data: clients } = useClientList();
  const createProject = useCreateProject();
  const updateProject = useUpdateProject();
  const deleteProject = useDeleteProject();

  const isSaving = createProject.isPending || updateProject.isPending;

  function openCreate() {
    setEditingProject(null);
    setForm(EMPTY_FORM);
    setDialogOpen(true);
  }

  function openEdit(project: DataProject) {
    setEditingProject(project);
    setForm({
      name: project.name,
      client_id: project.client_id ?? "",
      repo: project.repo ?? "",
    });
    setDialogOpen(true);
  }

  function handleSave() {
    const trimmedName = form.name.trim();
    if (!trimmedName) return;

    const body: {
      name: string;
      client_id?: string;
      repo?: string;
    } = {
      name: trimmedName,
    };

    if (form.client_id) {
      body.client_id = form.client_id;
    }

    const trimmedRepo = form.repo.trim();
    if (trimmedRepo) {
      body.repo = trimmedRepo;
    }

    if (editingProject) {
      updateProject.mutate(
        { id: editingProject.id, body },
        {
          onSuccess: () => {
            setDialogOpen(false);
            setEditingProject(null);
          },
        }
      );
    } else {
      createProject.mutate(body, {
        onSuccess: () => {
          setDialogOpen(false);
        },
      });
    }
  }

  function handleDelete(project: DataProject) {
    const confirmed = window.confirm(
      `Delete project "${project.name}"? This action cannot be undone.`
    );
    if (!confirmed) return;

    deleteProject.mutate(project.id, {
      onError: (error) => {
        if (error.message.includes("409")) {
          alert(
            "Cannot delete this project because it has associated work sessions. Remove or reassign the sessions first."
          );
        }
      },
    });
  }

  function handleClientFilterChange(value: string) {
    setSelectedClientId(value === "all" ? undefined : value);
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Projects</h2>
        <div className="flex items-center gap-3">
          <Select
            value={selectedClientId ?? "all"}
            onValueChange={handleClientFilterChange}
          >
            <SelectTrigger className="w-[200px]">
              <SelectValue placeholder="Filter by client" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Clients</SelectItem>
              {clients?.map((client) => (
                <SelectItem key={client.id} value={client.id}>
                  {client.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Button onClick={openCreate} size="sm">
            <Plus className="h-4 w-4 mr-1" />
            New Project
          </Button>
        </div>
      </div>

      {/* Table */}
      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : !projects?.length ? (
        <div className="text-center py-12 text-muted-foreground">
          No projects found.
        </div>
      ) : (
        <div className="border rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="text-left p-3 font-medium">Name</th>
                <th className="text-left p-3 font-medium">Client</th>
                <th className="text-left p-3 font-medium">Repo</th>
                <th className="text-right p-3 font-medium">Sessions</th>
                <th className="text-right p-3 font-medium">Total Hours</th>
                <th className="text-left p-3 font-medium">Last Activity</th>
                <th className="text-right p-3 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {projects.map((project) => (
                <tr
                  key={project.id}
                  className="border-b last:border-b-0 hover:bg-muted/30 transition-colors"
                >
                  <td className="p-3 font-medium">{project.name}</td>
                  <td className="p-3 text-muted-foreground">
                    {project.client_name ?? "—"}
                  </td>
                  <td className="p-3">
                    {project.repo ? (
                      <a
                        href={`https://github.com/${project.repo}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-blue-600 dark:text-blue-400 hover:underline"
                      >
                        {project.repo}
                        <ExternalLink className="h-3 w-3" />
                      </a>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </td>
                  <td className="p-3 text-right tabular-nums">
                    {project.session_count}
                  </td>
                  <td className="p-3 text-right tabular-nums">
                    {formatDuration(project.total_minutes)}
                  </td>
                  <td className="p-3 text-muted-foreground">
                    {project.last_activity
                      ? formatDate(project.last_activity)
                      : "—"}
                  </td>
                  <td className="p-3 text-right">
                    <div className="flex items-center justify-end gap-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8"
                        onClick={() => openEdit(project)}
                        title="Edit project"
                      >
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 text-destructive hover:text-destructive"
                        onClick={() => handleDelete(project)}
                        title="Delete project"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Create / Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {editingProject ? "Edit Project" : "New Project"}
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label htmlFor="project-name">Name</Label>
              <Input
                id="project-name"
                placeholder="Project name"
                value={form.name}
                onChange={(e) =>
                  setForm((prev) => ({ ...prev, name: e.target.value }))
                }
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="project-client">Client</Label>
              <Select
                value={form.client_id || "none"}
                onValueChange={(value) =>
                  setForm((prev) => ({
                    ...prev,
                    client_id: value === "none" ? "" : value,
                  }))
                }
              >
                <SelectTrigger id="project-client">
                  <SelectValue placeholder="Select a client" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">No client</SelectItem>
                  {clients?.map((client) => (
                    <SelectItem key={client.id} value={client.id}>
                      {client.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="project-repo">Repository</Label>
              <Input
                id="project-repo"
                placeholder="owner/repo"
                value={form.repo}
                onChange={(e) =>
                  setForm((prev) => ({ ...prev, repo: e.target.value }))
                }
              />
              <p className="text-xs text-muted-foreground">
                GitHub repository in owner/repo format (e.g. acme/my-project)
              </p>
            </div>
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDialogOpen(false)}
              disabled={isSaving}
            >
              Cancel
            </Button>
            <Button
              onClick={handleSave}
              disabled={!form.name.trim() || isSaving}
            >
              {isSaving && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              {editingProject ? "Save Changes" : "Create Project"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
