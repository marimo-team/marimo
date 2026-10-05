import type {
  AiModelCost,
  CAPABILITIES,
  ModelLimits,
  ReasoningOption,
} from "./metadata.ts";

export type { AiModelCost, ModelLimits, ReasoningOption } from "./metadata.ts";

export const ROLES = [
  "chat",
  "edit",
  "rerank",
  "embed",
  "autocomplete",
] as const;
export type Role = (typeof ROLES)[number];

type Capability = (typeof CAPABILITIES)[number];
type DataType = "text" | "image" | "pdf";

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
  /** Provider-specific controls; omitted when unknown. Does not select an effort. */
  reasoning_options?: ReasoningOption[];
  /** Token limits for this provider offering; omitted values are unknown. */
  limits?: ModelLimits;
}

export type SyncableProviderId =
  | "anthropic"
  | "openai"
  | "google"
  | "bedrock"
  | "azure"
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
