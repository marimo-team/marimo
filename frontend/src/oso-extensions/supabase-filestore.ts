import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import type { FileStore } from "@/core/wasm/store";
import type { FragmentStore } from "./fragment-store";

export class SupabaseFileStore implements FileStore {
  private client: SupabaseClient | null = null;
  private fragmentStore: FragmentStore;
  private notebookId: string | null = null;
  private organizationId: string | null = null;
  private userId: string | null = null;

  constructor(fragmentStore: FragmentStore) {
    this.fragmentStore = fragmentStore;
    this.initializeClient();
  }

  private initializeClient(): void {
    const envVars = this.fragmentStore.getJSON<Record<string, string>>(
      "env",
      {},
    );

    const supabaseUrl = envVars["SUPABASE_URL"];
    const jwtToken = envVars["SUPABASE_JWT_TOKEN"];
    this.notebookId = envVars["OSO_NOTEBOOK_ID"];
    this.organizationId = envVars["OSO_ORGANIZATION_ID"];

    const requiredVars = [
      supabaseUrl,
      jwtToken,
      this.notebookId,
      this.organizationId,
    ];
    if (!requiredVars.every(Boolean)) {
      return;
    }

    this.userId = this.extractUserIdFromJWT(jwtToken);
    this.client = createClient(supabaseUrl, jwtToken);
  }

  private extractUserIdFromJWT(token: string): string | null {
    try {
      const payload = token.split(".")[1];
      const decoded = JSON.parse(atob(payload)) as { sub?: string };
      return decoded.sub || null;
    } catch {
      return null;
    }
  }

  private get isConfigured(): boolean {
    return Boolean(this.client && this.notebookId && this.organizationId);
  }

  async saveFile(contents: string): Promise<void> {
    if (!this.isConfigured || !this.userId) {
      return;
    }

    const existingId = await this.findExistingRecord();
    const { error } = existingId
      ? await this.updateRecord(existingId, contents)
      : await this.createRecord(contents);

    if (error) {
      console.error("Failed to save file to Supabase:", error);
    }
  }

  private async findExistingRecord(): Promise<string | null> {
    const { data, error } = await this.client!
      .from("saved_queries")
      .select("id")
      .eq("org_id", this.organizationId!)
      .eq("display_name", this.notebookId!)
      .is("deleted_at", null)
      .single();

    if (error?.code === "PGRST116") {
      return null;
    }
    
    return data?.id || null;
  }

  private async updateRecord(id: string, contents: string) {
    return this.client!
      .from("saved_queries")
      .update({
        data: contents,
        updated_at: new Date().toISOString(),
      })
      .eq("id", id);
  }

  private async createRecord(contents: string) {
    return this.client!
      .from("saved_queries")
      .insert({
        org_id: this.organizationId!,
        display_name: this.notebookId!,
        data: contents,
        created_by: this.userId!,
      });
  }

  async readFile(): Promise<string | null> {
    if (!this.isConfigured) {
      return null;
    }

    const { data, error } = await this.client!
      .from("saved_queries")
      .select("data")
      .eq("org_id", this.organizationId!)
      .eq("display_name", this.notebookId!)
      .is("deleted_at", null)
      .single();

    if (error) {
      if (error.code === "PGRST116") {
        return null;
      }
      console.error("Failed to read file from Supabase:", error);
      return null;
    }

    return data?.data || null;
  }
}
