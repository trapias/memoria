"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Pencil, Trash2, Plus, Loader2, AlertCircle } from "lucide-react";
import {
  useClientList,
  useCreateClient,
  useUpdateClient,
  useDeleteClient,
  formatDuration,
  formatDate,
} from "@/lib/hooks/use-data";
import { type DataClient } from "@/lib/api";

interface ClientFormState {
  name: string;
  metadataJson: string;
}

const EMPTY_FORM: ClientFormState = {
  name: "",
  metadataJson: "{}",
};

export function ClientsTab() {
  const { data: clients, isLoading, error } = useClientList();
  const createClient = useCreateClient();
  const updateClient = useUpdateClient();
  const deleteClient = useDeleteClient();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingClient, setEditingClient] = useState<DataClient | null>(null);
  const [form, setForm] = useState<ClientFormState>(EMPTY_FORM);
  const [jsonError, setJsonError] = useState<string | null>(null);

  function openCreateDialog() {
    setEditingClient(null);
    setForm(EMPTY_FORM);
    setJsonError(null);
    setDialogOpen(true);
  }

  function openEditDialog(client: DataClient) {
    setEditingClient(client);
    setForm({
      name: client.name,
      metadataJson: JSON.stringify(client.metadata ?? {}, null, 2),
    });
    setJsonError(null);
    setDialogOpen(true);
  }

  function closeDialog() {
    setDialogOpen(false);
    setEditingClient(null);
    setForm(EMPTY_FORM);
    setJsonError(null);
  }

  async function handleSave() {
    let metadata: Record<string, unknown>;
    try {
      metadata = JSON.parse(form.metadataJson);
    } catch {
      setJsonError("Invalid JSON. Please check the syntax.");
      return;
    }

    if (!form.name.trim()) {
      return;
    }

    try {
      if (editingClient) {
        await updateClient.mutateAsync({
          id: editingClient.id,
          body: { name: form.name.trim(), metadata },
        });
      } else {
        await createClient.mutateAsync({
          name: form.name.trim(),
          metadata,
        });
      }
      closeDialog();
    } catch {
      // mutation error is handled by react-query
    }
  }

  async function handleDelete(client: DataClient) {
    const confirmed = window.confirm(
      `Are you sure you want to delete client "${client.name}"?`
    );
    if (!confirmed) return;

    try {
      await deleteClient.mutateAsync(client.id);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to delete client";
      if (message.includes("409")) {
        alert(
          `Cannot delete "${client.name}": this client has associated sessions. Remove the sessions first.`
        );
      } else {
        alert(`Error deleting client: ${message}`);
      }
    }
  }

  const isSaving = createClient.isPending || updateClient.isPending;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        <span className="ml-2 text-muted-foreground">Loading clients...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-destructive">
        <AlertCircle className="h-5 w-5 shrink-0" />
        <p>Failed to load clients: {error.message}</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Clients</h2>
        <Button size="sm" onClick={openCreateDialog}>
          <Plus className="mr-1 h-4 w-4" />
          New Client
        </Button>
      </div>

      {/* Table */}
      {clients && clients.length > 0 ? (
        <div className="rounded-md border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="px-4 py-3 text-left font-medium">Name</th>
                <th className="px-4 py-3 text-right font-medium">Projects</th>
                <th className="px-4 py-3 text-right font-medium">Sessions</th>
                <th className="px-4 py-3 text-right font-medium">
                  Total Hours
                </th>
                <th className="px-4 py-3 text-left font-medium">
                  Last Activity
                </th>
                <th className="px-4 py-3 text-right font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {clients.map((client) => (
                <tr
                  key={client.id}
                  className="border-b last:border-b-0 hover:bg-muted/30 transition-colors"
                >
                  <td className="px-4 py-3 font-medium">{client.name}</td>
                  <td className="px-4 py-3 text-right tabular-nums">
                    {client.project_count}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums">
                    {client.session_count}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums">
                    {formatDuration(client.total_minutes)}
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {client.last_activity
                      ? formatDate(client.last_activity)
                      : "\u2014"}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8"
                        onClick={() => openEditDialog(client)}
                        aria-label={`Edit ${client.name}`}
                      >
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 text-destructive hover:text-destructive"
                        onClick={() => handleDelete(client)}
                        disabled={deleteClient.isPending}
                        aria-label={`Delete ${client.name}`}
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
      ) : (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed py-12 text-center">
          <p className="text-muted-foreground">No clients yet.</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Create your first client to start tracking work.
          </p>
          <Button size="sm" variant="outline" className="mt-4" onClick={openCreateDialog}>
            <Plus className="mr-1 h-4 w-4" />
            New Client
          </Button>
        </div>
      )}

      {/* Create / Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={(open) => !open && closeDialog()}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>
              {editingClient ? "Edit Client" : "New Client"}
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label htmlFor="client-name">Name</Label>
              <Input
                id="client-name"
                placeholder="Client name"
                value={form.name}
                onChange={(e) =>
                  setForm((prev) => ({ ...prev, name: e.target.value }))
                }
                autoFocus
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="client-metadata">Metadata (JSON)</Label>
              <textarea
                id="client-metadata"
                className="flex min-h-[120px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 font-mono"
                placeholder="{}"
                value={form.metadataJson}
                onChange={(e) => {
                  setForm((prev) => ({
                    ...prev,
                    metadataJson: e.target.value,
                  }));
                  setJsonError(null);
                }}
              />
              {jsonError && (
                <p className="text-sm text-destructive flex items-center gap-1">
                  <AlertCircle className="h-3.5 w-3.5 shrink-0" />
                  {jsonError}
                </p>
              )}
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={closeDialog} disabled={isSaving}>
              Cancel
            </Button>
            <Button
              onClick={handleSave}
              disabled={isSaving || !form.name.trim()}
            >
              {isSaving && <Loader2 className="mr-1 h-4 w-4 animate-spin" />}
              {editingClient ? "Save Changes" : "Create"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
