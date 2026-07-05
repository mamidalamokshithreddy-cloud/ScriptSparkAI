import { API_BASE_URL } from "@/config/api";

export interface Scene {
  dialogue?: string | unknown[];
  header?: string;
  narration?: unknown;
  scene_number: number;
  description: string;
  location?: string;
  time?: string;
  characters?: string[];
  visual_description?: string;
  character_action?: string;
  emotional_shift?: string;
  camera_suggestion?: string;
  lighting?: string;
  background_music?: string;
  color_palette?: string[];
  shot_list?: string[];
  production_note?: string;
}

export interface StoryResponse {
  genre: string;
  length_minutes: number;
  logline?: string;
  summary?: string;
  characters: any[];
  character_profiles?: any[];
  themes?: string[];
  tone?: string;
  target_audience?: string;
  estimated_runtime?: string;
  scene_count?: number;
  title: string;
  language: string;
  scenes: Scene[];
  voiceover?: {
    style?: string;
    sample?: string;
    narration_text?: string;
  };
  screenplay?: string;
  scene_breakdown?: any[];
  dialogues?: any[];
  shot_list?: string[];
  camera_suggestions?: string[];
  lighting_suggestions?: string[];
  background_music_suggestions?: string[];
  production_notes?: string[];
  poster_prompt?: string;
  background_music?: string;
  camera_style?: string;
  color_palette?: string[];
  metadata?: Record<string, unknown>;
}

export const generateStory = async (payload: any): Promise<StoryResponse> => {
  const res = await fetch(`${API_BASE_URL}/api/story/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(`Story generation failed: ${errorText}`);
  }

  return res.json();
};

export const generateVoiceover = async (
  text: string,
  voice = "bella",
  language = "English"
): Promise<Blob> => {
  const res = await fetch(`${API_BASE_URL}/api/story/voiceover`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, voice, language }),
  });

  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(`Voiceover generation failed: ${errorText}`);
  }

  return res.blob();
};
