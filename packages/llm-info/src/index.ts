export interface AiModel {
  name: string;
  model: string;
  description: string;
  providers: string[];
  roles: string[];
  thinking: boolean;
}

export interface AiProvider {
  name: string;
  id: string;
  description: string;
  url: string;
}
