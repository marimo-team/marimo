import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import type { FileStore } from "@/core/wasm/store";
import type { FragmentStore } from "./fragment-store";

export class SupabaseFileStore implements FileStore {
  private client: SupabaseClient | null = null;
  private fragmentStore: FragmentStore;
  private notebookName: string | null = null;
  private organizationName: string | null = null;
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
    const anonKey = envVars["SUPABASE_ANON_KEY"];
    this.notebookName = envVars["OSO_NOTEBOOK_NAME"];
    this.organizationName = envVars["OSO_ORGANIZATION_NAME"];

    const requiredVars = [
      supabaseUrl,
      jwtToken,
      anonKey,
      this.notebookName,
      this.organizationName,
    ];
    if (!requiredVars.every(Boolean)) {
      return;
    }

    this.userId = this.extractUserIdFromJWT(jwtToken);
    this.client = createClient(supabaseUrl, anonKey, {
      global: { headers: { Authorization: `Bearer ${jwtToken}` } },
    });
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
    return Boolean(this.client && this.notebookName && this.organizationName);
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
    const orgId = await this.getOrganizationId();
    if (!orgId) {
      return null;
    }

    const { data, error } = await this.client!
      .from("notebooks")
      .select("id")
      .eq("org_id", orgId)
      .eq("notebook_name", this.notebookName!)
      .is("deleted_at", null)
      .single();

    if (error?.code === "PGRST116") {
      return null;
    }

    return data?.id || null;
  }

  private async getOrganizationId(): Promise<string | null> {
    const { data, error } = await this.client!
      .from("organizations")
      .select("id")
      .eq("org_name", this.organizationName!)
      .is("deleted_at", null)
      .single();

    if (error) {
      return null;
    }

    return data?.id || null;
  }

  private async updateRecord(id: string, contents: string) {
    return this.client!
      .from("notebooks")
      .update({
        data: contents,
        updated_at: new Date().toISOString(),
      })
      .eq("id", id);
  }

  private async createRecord(contents: string) {
    const orgId = await this.getOrganizationId();
    if (!orgId) {
      throw new Error(`Organization not found: ${this.organizationName}`);
    }

    return this.client!
      .from("notebooks")
      .insert({
        org_id: orgId,
        notebook_name: this.notebookName!,
        data: contents,
        created_by: this.userId!,
      });
  }

  async readFile(): Promise<string | null> {
    if (!this.isConfigured) {
      return null;
    }

    const orgId = await this.getOrganizationId();
    if (!orgId) {
      return null;
    }

    const { data, error } = await this.client!
      .from("notebooks")
      .select("data")
      .eq("org_id", orgId)
      .eq("notebook_name", this.notebookName!)
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
