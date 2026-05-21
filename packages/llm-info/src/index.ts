export const ROLES = [
  "chat",
  "edit",
  "rerank",
  "embed",
  "autocomplete",
] as const;
export type Role = (typeof ROLES)[number];

type Capability = "thinking" | "tool_calling";
type DataType = "text" | "image" | "pdf";

/**
 * Per-token pricing in USD per 1M tokens, mirroring the `cost` block on
 * `models.dev`. All fields are optional — open-weights / self-hosted models
 * usually have none.
 */
export interface AiModelCost {
  input?: number;
  output?: number;
}

export interface AiModel {
  name: string;
  model: string;
  description: string;
  roles: Role[];
  capabilities: Capability[];
  input_types: DataType[];
  output_types: DataType[];
  /** ISO `YYYY-MM-DD` — stored as a string to round-trip through YAML/JSON. */
  release_date: string;
  cost?: AiModelCost;
}

export type SyncableProviderId =
  | "anthropic"
  | "openai"
  | "google"
  | "bedrock"
  | "azure"
  | "github"
  | "ollama"
  | "wandb"
  | "opencode-go";

/**
 * `models.yml` and `models.json` are keyed by provider id at the top level —
 * the same model may appear under multiple providers as independent entries.
 */
export type ModelsByProvider = Partial<Record<SyncableProviderId, AiModel[]>>;

export interface AiProvider {
  name: string;
  id: string;
  description: string;
  url: string;
}
