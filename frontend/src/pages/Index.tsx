import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Slider } from '@/components/ui/slider';
import { Switch } from '@/components/ui/switch';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Download, Share, Edit, RefreshCw, Home, FileText, Mic, X, CheckCircle, AlertCircle, MapPin, Clock, Users, MessageSquare, Eye, Heart, Camera, Sun, Music, Palette } from 'lucide-react';
import { generateStory, generateVoiceover } from '@/api/story';

const ENABLE_AUTO_VOICEOVER = import.meta.env.VITE_ENABLE_AUTO_VOICEOVER === 'true';

interface StoryScene {
  scene_number: number;
  description: string;
  location?: string;
  time?: string;
  characters?: string[];
  visual_description?: string;
  character_action?: string;
  dialogue?: string;
  emotional_shift?: string;
  camera_suggestion?: string;
  lighting?: string;
  background_music?: string;
  color_palette?: string[];
  shot_list?: string[];
  production_note?: string;
}

interface Story {
  title: string;
  genre?: string;
  language: string;
  logline?: string;
  summary?: string;
  characters?: any[];
  character_profiles?: any[];
  screenplay?: string;
  scene_breakdown?: any[];
  dialogues?: any[];
  shot_list?: string[];
  camera_suggestions?: string[];
  lighting_suggestions?: string[];
  background_music_suggestions?: string[];
  production_notes?: string[];
  poster_prompt?: string;
  voiceover?: {
    style?: string;
    sample?: string;
    narration_text?: string;
  };
  tone?: string;
  estimated_runtime?: string;
  background_music?: string;
  camera_style?: string;
  color_palette?: string[];
  scenes: StoryScene[];
}

interface StoryData {
  prompt: string;
  genre: string;
  length: [number];
  themes: string[];
  useFactRetrieval: boolean;
  language: string;
}

const convertToScreenplay = (story: Story | null): string => {
  if (!story) return "No story generated yet.";
  if (story.screenplay) return story.screenplay;
  let result = `# ${story.title || 'Untitled Story'}\n\n`;
  result += `**Language:** ${story.language || 'Not specified'}\n\n`;
  story.scenes?.forEach((scene) => {
    result += `## Scene ${scene.scene_number}\n\n`;
    result += `${scene.description || 'No description available'}\n\n`;
    result += `---\n\n`;
  });
  return result;
};

const convertToFountain = (story: Story | null): string => {
  if (!story) return "No story generated yet.";
  if (story.screenplay) return story.screenplay;
  let result = `Title: ${story.title || 'Untitled Story'}\n`;
  result += `Language: ${story.language || 'Not specified'}\n\n`;
  story.scenes?.forEach((scene) => {
    result += `\n.SCENE ${scene.scene_number}\n\n`;
    result += `${(scene.description || 'No description available').toUpperCase()}\n\n`;
  });
  return result;
};

const Index = () => {
  const [currentScreen, setCurrentScreen] = useState<'home' | 'builder' | 'preview' | 'script' | 'addons' | 'export'>('home');
  const [storyData, setStoryData] = useState<StoryData>({
    prompt: '',
    genre: '',
    length: [5],
    themes: [],
    useFactRetrieval: true,
    language: 'English'
  });
  const [generatedStory, setGeneratedStory] = useState<Story | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generationStage, setGenerationStage] = useState('');
  const [toasts, setToasts] = useState<Array<{
    id: number;
    title: string;
    description?: string;
    variant?: 'destructive';
  }>>([]);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);

  const genres = ['Drama', 'Thriller', 'Satire', 'Romance', 'Mythology'];
  const themes = ['Freedom', 'Family', 'Sacrifice', 'Revenge', 'Humor'];
  const languages = [
    { value: 'english', label: 'English' },
    { value: 'telugu', label: 'Telugu' },
    { value: 'hindi', label: 'Hindi' }
  ];

  const showToast = (toast: { title: string; description?: string; variant?: 'destructive' }) => {
    const id = Date.now();
    setToasts(prev => [...prev, { ...toast, id }]);
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 5000);
  };

  const sleep = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

  const handleThemeToggle = (theme: string) => {
    setStoryData(prev => ({
      ...prev,
      themes: prev.themes.includes(theme) 
        ? prev.themes.filter(t => t !== theme) 
        : [...prev.themes, theme]
    }));
  };

  const handleGenerate = async () => {
    if (!storyData.prompt || storyData.prompt.length < 10) {
      showToast({
        title: "Please enter a story prompt",
        description: "Your prompt should be at least 10 characters long.",
        variant: "destructive"
      });
      return;
    }

    setIsGenerating(true);
    setGenerationStage('Writing cinematic treatment...');
    setGeneratedStory(null);
    setAudioUrl(null);
    setCurrentScreen('preview');

    try {
      const response = await generateStory({
        prompt: storyData.prompt,
        genre: storyData.genre,
        length_minutes: storyData.length[0],
        language: storyData.language,
        themes: storyData.themes,
        use_real_world_context: storyData.useFactRetrieval,
      });

      // Preserve original Unicode characters without unnecessary transformations
      const transformedStory: Story = {
        title: response.title || "Untitled Story",
        genre: response.genre || storyData.genre,
        language: response.language || storyData.language,
        logline: response.logline,
        summary: response.summary,
        characters: response.characters,
        character_profiles: response.character_profiles,
        screenplay: response.screenplay,
        scene_breakdown: response.scene_breakdown,
        dialogues: response.dialogues,
        shot_list: response.shot_list,
        camera_suggestions: response.camera_suggestions,
        lighting_suggestions: response.lighting_suggestions,
        background_music_suggestions: response.background_music_suggestions,
        production_notes: response.production_notes,
        poster_prompt: response.poster_prompt,
        voiceover: response.voiceover,
        tone: response.tone,
        estimated_runtime: response.estimated_runtime,
        background_music: response.background_music,
        camera_style: response.camera_style,
        color_palette: response.color_palette,
        scenes: response.scenes.map(scene => ({
          scene_number: scene.scene_number || 0,
          description: scene.description || "No description available",
          location: scene.location,
          time: scene.time,
          characters: scene.characters,
          visual_description: scene.visual_description,
          character_action: scene.character_action,
          dialogue: typeof scene.dialogue === 'string' ? scene.dialogue : '',
          emotional_shift: scene.emotional_shift,
          camera_suggestion: scene.camera_suggestion,
          lighting: scene.lighting,
          background_music: scene.background_music,
          color_palette: scene.color_palette,
          shot_list: scene.shot_list,
          production_note: scene.production_note
        }))
      };

      setGenerationStage('Streaming scenes...');
      setGeneratedStory({ ...transformedStory, scenes: [] });
      for (const scene of transformedStory.scenes) {
        await sleep(180);
        setGeneratedStory(prev => prev ? { ...prev, scenes: [...prev.scenes, scene] } : prev);
      }

      const narrationText = transformedStory.voiceover?.narration_text?.trim();
      if (ENABLE_AUTO_VOICEOVER && narrationText) {
        try {
          const audioBlob = await generateVoiceover(narrationText, 'bella', storyData.language);
          setAudioUrl(URL.createObjectURL(audioBlob));
        } catch (voiceErr) {
          console.warn("Voiceover unavailable:", voiceErr);
          showToast({
            title: "Story generated; voiceover unavailable",
            description: "Add an ElevenLabs API key to enable audio."
          });
        }
      }
      
      showToast({
        title: "Story generated successfully!",
        description: "Your story is ready for review."
      });
    } catch (err) {
      console.error("Story generation error:", err);
      showToast({
        title: "Error",
        description: "Story generation failed. Please try again.",
        variant: "destructive"
      });
    } finally {
      setIsGenerating(false);
      setGenerationStage('');
    }
  };

  const handleDownload = (format: 'fountain' | 'markdown' | 'json') => {
    if (!generatedStory) {
      showToast({
        title: "No story to download",
        variant: "destructive"
      });
      return;
    }

    let content = '';
    let filename = `${generatedStory.title?.replace(/\s+/g, '_') || 'untitled_story'}`;
    let mimeType = 'text/plain';

    switch (format) {
      case 'fountain':
        content = convertToFountain(generatedStory);
        filename += '.fountain';
        break;
      case 'markdown':
        content = convertToScreenplay(generatedStory);
        filename += '.md';
        break;
      case 'json':
        content = JSON.stringify(generatedStory, null, 2);
        filename += '.json';
        mimeType = 'application/json';
        break;
    }

    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const DetailItem = ({ icon: Icon, label, value }: { icon: any; label: string; value?: string | string[] }) => {
    const displayValue = Array.isArray(value) ? value.join(', ') : value;
    if (!displayValue) return null;
    return (
      <div className="rounded-md border border-slate-200 bg-white/80 p-4">
        <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
          <Icon className="h-4 w-4 text-orange-600" />
          {label}
        </div>
        <div className="whitespace-pre-wrap text-sm leading-6 text-slate-800">{displayValue}</div>
      </div>
    );
  };

  const PaletteSwatches = ({ colors }: { colors?: string[] }) => {
    if (!colors?.length) return null;
    return (
      <div className="rounded-md border border-slate-200 bg-white/80 p-4">
        <div className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
          <Palette className="h-4 w-4 text-orange-600" />
          Color Palette
        </div>
        <div className="flex flex-wrap gap-2">
          {colors.map((color) => (
            <span key={color} className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-medium text-slate-700">
              {color}
            </span>
          ))}
        </div>
      </div>
    );
  };

  const SceneLoadingSkeleton = () => (
    <div className="space-y-5">
      {[1, 2, 3].map(item => (
        <div key={item} className="animate-pulse rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
          <div className="mb-5 h-5 w-36 rounded bg-slate-200" />
          <div className="grid gap-4 md:grid-cols-2">
            <div className="h-24 rounded bg-slate-100" />
            <div className="h-24 rounded bg-slate-100" />
            <div className="h-24 rounded bg-slate-100" />
            <div className="h-24 rounded bg-slate-100" />
          </div>
        </div>
      ))}
    </div>
  );

  const renderHomeScreen = () => (
    <div className="min-h-screen bg-gradient-to-br from-orange-50 via-red-50 to-yellow-50">
      <div className="container mx-auto px-4 py-16">
        <div className="text-center mb-16">
          <div className="mb-8">
            <h1 className="text-6xl font-bold bg-gradient-to-r from-orange-600 via-red-600 to-yellow-600 bg-clip-text text-transparent mb-4">ScriptSpark</h1>
            <p className="text-2xl text-gray-700 font-medium">AI Story Generator for Creators</p>
          </div>
          <div className="max-w-2xl mx-auto mb-12">
            <h2 className="text-3xl font-bold text-gray-800 mb-4">Generate compelling, culturally rooted stories in seconds</h2>
            <p className="text-lg text-gray-600 mb-8">Powered by Gemini, LangChain, and real-world retrieval</p>
            <Button 
              onClick={() => setCurrentScreen('builder')} 
              size="lg" 
              className="text-xl px-8 py-6 bg-gradient-to-r from-orange-600 to-red-600 hover:from-orange-700 hover:to-red-700 shadow-lg hover:shadow-xl transition-all duration-300"
            >
              <FileText className="mr-2 h-5 w-5" />Start Creating
            </Button>
          </div>
        </div>
        <div className="grid md:grid-cols-3 gap-8 max-w-6xl mx-auto">
          <Card className="border-orange-200 shadow-lg hover:shadow-xl transition-shadow">
            <CardHeader><CardTitle className="text-orange-700">AI-Powered Generation</CardTitle></CardHeader>
            <CardContent><p className="text-gray-600">Creates stories grounded in culture and history</p></CardContent>
          </Card>
          <Card className="border-red-200 shadow-lg hover:shadow-xl transition-shadow">
            <CardHeader><CardTitle className="text-red-700">Multiple Formats</CardTitle></CardHeader>
            <CardContent><p className="text-gray-600">Export as screenplay, markdown, or JSON</p></CardContent>
          </Card>
          <Card className="border-yellow-200 shadow-lg hover:shadow-xl transition-shadow">
            <CardHeader><CardTitle className="text-yellow-700">Cultural Context</CardTitle></CardHeader>
            <CardContent><p className="text-gray-600">Enriched with authentic traditions</p></CardContent>
          </Card>
        </div>
      </div>
    </div>
  );

  const renderBuilderScreen = () => (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-orange-50">
      <div className="container mx-auto px-4 py-8">
        <div className="max-w-4xl mx-auto">
          <div className="mb-8">
            <Button variant="ghost" onClick={() => setCurrentScreen('home')} className="mb-4">
              <Home className="w-4 h-4 mr-2" />Back to Home
            </Button>
            <h1 className="text-4xl font-bold text-gray-800 mb-2">Story Prompt Builder</h1>
            <p className="text-gray-600">Craft your story with AI-powered generation</p>
          </div>
          <Card className="shadow-xl">
            <CardContent className="p-8">
              <div className="space-y-8">
                <div>
                  <Label htmlFor="prompt" className="text-lg font-semibold mb-3 block">Story Prompt *</Label>
                  <Textarea 
                    id="prompt" 
                    placeholder="Type your story idea..." 
                    value={storyData.prompt} 
                    onChange={(e) => setStoryData(prev => ({ ...prev, prompt: e.target.value }))} 
                    className="min-h-[120px] text-lg" 
                  />
                  <p className="text-sm text-gray-500 mt-2">Minimum 10 characters required</p>
                </div>
                <div className="grid md:grid-cols-2 gap-8">
                  <div>
                    <Label className="text-lg font-semibold mb-3 block">Genre</Label>
                    <Select 
                      value={storyData.genre} 
                      onValueChange={(value) => setStoryData(prev => ({ ...prev, genre: value }))}
                    >
                      <SelectTrigger className="text-lg">
                        <SelectValue placeholder="Select a genre" />
                      </SelectTrigger>
                      <SelectContent>
                        {genres.map(genre => (
                          <SelectItem key={genre} value={genre.toLowerCase()}>{genre}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label className="text-lg font-semibold mb-3 block">Story Length: {storyData.length[0]} minutes</Label>
                    <Slider 
                      value={storyData.length} 
                      onValueChange={(value) => setStoryData(prev => ({ ...prev, length: [value[0]] }))} 
                      max={10} 
                      min={1} 
                      step={1} 
                      className="mt-4" 
                    />
                  </div>
                </div>
                <div>
                  <Label className="text-lg font-semibold mb-3 block">Themes</Label>
                  <div className="flex flex-wrap gap-3">
                    {themes.map(theme => (
                      <Badge 
                        key={theme} 
                        variant={storyData.themes.includes(theme) ? "default" : "outline"} 
                        className="cursor-pointer px-4 py-2 text-sm hover:bg-orange-100" 
                        onClick={() => handleThemeToggle(theme)}
                      >
                        {theme}
                      </Badge>
                    ))}
                  </div>
                </div>
                <div className="grid md:grid-cols-2 gap-8">
                  <div className="flex items-center space-x-3">
                    <Switch 
                      id="fact-retrieval" 
                      checked={storyData.useFactRetrieval} 
                      onCheckedChange={(checked) => setStoryData(prev => ({ ...prev, useFactRetrieval: checked }))} 
                    />
                    <Label htmlFor="fact-retrieval" className="text-lg font-semibold">Enable Real-World Fact Retrieval</Label>
                  </div>
                  <div>
                    <Label className="text-lg font-semibold mb-3 block">Output Language</Label>
                    <Select 
                      value={storyData.language} 
                      onValueChange={(value) => setStoryData(prev => ({ ...prev, language: value }))}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Select language" />
                      </SelectTrigger>
                      <SelectContent>
                        {languages.map(lang => (
                          <SelectItem key={lang.value} value={lang.value}>{lang.label}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <Button 
                  onClick={handleGenerate} 
                  disabled={isGenerating} 
                  size="lg" 
                  className="w-full text-xl py-6 bg-gradient-to-r from-orange-600 to-red-600 hover:from-orange-700 hover:to-red-700"
                >
                  {isGenerating ? (
                    <>
                      <RefreshCw className="w-5 h-5 mr-2 animate-spin" />
                      Generating Story...
                    </>
                  ) : 'Generate Story'}
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );

  const renderPreviewScreen = () => (
    <div className="min-h-screen bg-[#f8f5f0]">
      <div className="container mx-auto px-4 py-6 md:py-8">
        <div className="mx-auto max-w-7xl">
          <div className="mb-6">
            <Button variant="ghost" onClick={() => setCurrentScreen('builder')} className="mb-4">
              <Edit className="w-4 h-4 mr-2" />Back to Builder
            </Button>
            <div className="space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                {generatedStory?.genre && <Badge variant="secondary">{generatedStory.genre}</Badge>}
                {generatedStory?.estimated_runtime && <Badge variant="outline">{generatedStory.estimated_runtime}</Badge>}
                {generatedStory?.tone && <Badge variant="outline">{generatedStory.tone}</Badge>}
              </div>
              <h1 className="text-3xl font-bold leading-tight text-slate-950 md:text-5xl">{generatedStory?.title ?? 'Writing your story...'}</h1>
              <p className="max-w-3xl text-base leading-7 text-slate-600 md:text-lg">
                {generatedStory?.logline || generationStage || 'A cinematic screenplay treatment is being prepared.'}
              </p>
            </div>
          </div>

          {generatedStory?.summary && (
            <div className="mb-6 rounded-lg border border-slate-200 bg-white/80 p-5 shadow-sm">
              <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Summary</div>
              <p className="text-sm leading-7 text-slate-700 md:text-base">{generatedStory.summary}</p>
            </div>
          )}

          <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
            <div>
              {isGenerating && !generatedStory?.scenes.length ? (
                <SceneLoadingSkeleton />
              ) : (
                <div className="space-y-5">
                  {(generatedStory?.scenes ?? []).map((scene, index) => {
                    const scenePalette = scene.color_palette?.length ? scene.color_palette : generatedStory?.color_palette;
                    return (
                      <Card key={`${scene.scene_number}-${index}`} className="overflow-hidden border-slate-200 bg-white shadow-md transition-all duration-300 hover:shadow-lg">
                        <CardHeader className="border-b border-slate-100 bg-slate-950 text-white">
                          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                            <CardTitle className="text-xl">Scene {scene.scene_number}</CardTitle>
                            <div className="flex flex-wrap gap-2 text-xs">
                              {scene.location && <span className="rounded-full bg-white/10 px-3 py-1">{scene.location}</span>}
                              {scene.time && <span className="rounded-full bg-white/10 px-3 py-1">{scene.time}</span>}
                            </div>
                          </div>
                        </CardHeader>
                        <CardContent className="space-y-5 p-5 md:p-6">
                          <div className="grid gap-4 md:grid-cols-2">
                            <DetailItem icon={MapPin} label="Location" value={scene.location} />
                            <DetailItem icon={Clock} label="Time" value={scene.time} />
                            <DetailItem icon={Users} label="Characters" value={scene.characters} />
                            <DetailItem icon={MessageSquare} label="Dialogue" value={scene.dialogue} />
                            <DetailItem icon={Eye} label="Visual Description" value={scene.visual_description} />
                            <DetailItem icon={Heart} label="Emotion" value={scene.emotional_shift} />
                            <DetailItem icon={Camera} label="Camera Shot" value={scene.camera_suggestion} />
                            <DetailItem icon={Sun} label="Lighting" value={scene.lighting} />
                            <DetailItem icon={Music} label="Background Music" value={scene.background_music || generatedStory?.background_music} />
                            <DetailItem icon={Camera} label="Shot List" value={scene.shot_list} />
                            <PaletteSwatches colors={scenePalette} />
                          </div>
                          {scene.character_action && (
                            <div className="rounded-md bg-orange-50 p-4 text-sm leading-7 text-slate-800">
                              <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-orange-700">Character Action</div>
                              {scene.character_action}
                            </div>
                          )}
                          {scene.production_note && (
                            <div className="rounded-md bg-slate-50 p-4 text-sm leading-7 text-slate-800">
                              <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-600">Production Note</div>
                              {scene.production_note}
                            </div>
                          )}
                        </CardContent>
                      </Card>
                    );
                  })}
                  {isGenerating && generatedStory?.scenes.length ? (
                    <div className="rounded-lg border border-dashed border-orange-300 bg-orange-50 p-4 text-sm text-orange-800">
                      <RefreshCw className="mr-2 inline h-4 w-4 animate-spin" />
                      {generationStage || 'Streaming remaining scenes...'}
                    </div>
                  ) : null}
                </div>
              )}
              {audioUrl && (
                <Card className="mt-6">
                  <CardHeader>
                    <CardTitle>Audio Preview</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <audio controls src={audioUrl} className="w-full" />
                  </CardContent>
                </Card>
              )}
              <div className="mt-8 flex flex-wrap gap-4">
                <Button onClick={() => setCurrentScreen('script')} size="lg">
                  <FileText className="w-4 h-4 mr-2" />Continue to Script View
                </Button>
                <Button variant="outline" onClick={handleGenerate}>
                  <RefreshCw className="w-4 h-4 mr-2" />Regenerate
                </Button>
                <Button variant="outline" onClick={() => setCurrentScreen('builder')}>
                  <Edit className="w-4 h-4 mr-2" />Edit Prompt
                </Button>
              </div>
            </div>
            <aside className="space-y-4">
              <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
                <div className="mb-3 text-sm font-semibold text-slate-950">Production Notes</div>
                <DetailItem icon={Music} label="Overall Music" value={generatedStory?.background_music} />
                <div className="mt-4">
                  <DetailItem icon={FileText} label="Production Notes" value={generatedStory?.production_notes} />
                </div>
                <div className="mt-4">
                  <DetailItem icon={Camera} label="Shot List" value={generatedStory?.shot_list} />
                </div>
                <div className="mt-4">
                  <DetailItem icon={Sun} label="Lighting Suggestions" value={generatedStory?.lighting_suggestions} />
                </div>
                <div className="mt-4">
                  <DetailItem icon={Camera} label="Camera Style" value={generatedStory?.camera_style} />
                </div>
                <div className="mt-4">
                  <PaletteSwatches colors={generatedStory?.color_palette} />
                </div>
                {generatedStory?.voiceover?.narration_text && (
                  <div className="mt-4">
                    <DetailItem icon={Mic} label="Voiceover Narration" value={generatedStory.voiceover.narration_text} />
                  </div>
                )}
              </div>
            </aside>
          </div>
        </div>
      </div>
    </div>
  );

  const renderScriptScreen = () => (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-orange-50">
      <div className="container mx-auto px-4 py-8">
        <div className="max-w-6xl mx-auto">
          <div className="mb-8">
            <Button variant="ghost" onClick={() => setCurrentScreen('preview')} className="mb-4">
              Back to Preview
            </Button>
            <h1 className="text-4xl font-bold text-gray-800 mb-2">Script Output</h1>
            <p className="text-gray-600">Professional screenplay format</p>
          </div>
          <Card className="shadow-xl">
            <CardContent className="p-0">
              <Tabs defaultValue="screenplay" className="w-full">
                <div className="border-b p-6">
                  <TabsList className="grid w-full max-w-md grid-cols-3">
                    <TabsTrigger value="screenplay">Screenplay</TabsTrigger>
                    <TabsTrigger value="markdown">Markdown</TabsTrigger>
                    <TabsTrigger value="json">JSON</TabsTrigger>
                  </TabsList>
                </div>
                <TabsContent value="screenplay" className="p-6">
                  <div className="bg-white p-8 rounded border font-sans text-sm leading-relaxed max-h-[60vh] overflow-y-auto whitespace-pre-wrap">
                    {convertToFountain(generatedStory)}
                  </div>
                </TabsContent>
                <TabsContent value="markdown" className="p-6">
                  <div className="bg-gray-100 p-6 rounded font-sans text-sm max-h-[60vh] overflow-y-auto whitespace-pre-wrap">
                    {convertToScreenplay(generatedStory)}
                  </div>
                </TabsContent>
                <TabsContent value="json" className="p-6">
                  <div className="bg-gray-100 p-6 rounded font-mono text-sm max-h-[60vh] overflow-y-auto">
                    <pre>{generatedStory ? JSON.stringify(generatedStory, null, 2) : 'No story data'}</pre>
                  </div>
                </TabsContent>
              </Tabs>
              <div className="border-t p-6">
                <div className="flex flex-wrap gap-4">
                  <Button onClick={() => handleDownload('fountain')} disabled={!generatedStory}>
                    <Download className="w-4 h-4 mr-2" />Download .fountain
                  </Button>
                  <Button variant="outline" onClick={() => handleDownload('markdown')} disabled={!generatedStory}>
                    <Download className="w-4 h-4 mr-2" />Download .md
                  </Button>
                  <Button variant="outline" onClick={() => handleDownload('json')} disabled={!generatedStory}>
                    <Download className="w-4 h-4 mr-2" />Download JSON
                  </Button>
                  <Button variant="outline" onClick={() => setCurrentScreen('addons')} disabled={!generatedStory}>
                    <Mic className="w-4 h-4 mr-2" />Add Voice
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );

  const renderAddonsScreen = () => (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-orange-50">
      <div className="container mx-auto px-4 py-8">
        <div className="max-w-4xl mx-auto">
          <div className="mb-8">
            <Button variant="ghost" onClick={() => setCurrentScreen('script')} className="mb-4">
              Back to Script
            </Button>
            <h1 className="text-4xl font-bold text-gray-800 mb-2">Enhance Your Story</h1>
            <p className="text-gray-600">Add visual and audio elements</p>
          </div>
          <div className="grid md:grid-cols-2 gap-8">
            <Card className="shadow-lg">
              <CardHeader>
                <CardTitle className="text-orange-700">AI Poster Generator</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="bg-gray-200 h-64 rounded-lg flex items-center justify-center mb-4">
                  <p className="text-gray-500">Poster Preview</p>
                </div>
                <div className="bg-gray-50 p-4 rounded mb-4">
                  <p className="text-sm font-mono">Auto-generated prompt:</p>
                  <p className="text-xs text-gray-600 mt-2">{generatedStory?.poster_prompt || 'Generate a story first to create a poster prompt.'}</p>
                </div>
                <Button className="w-full">
                  <Download className="w-4 h-4 mr-2" />Download Poster
                </Button>
              </CardContent>
            </Card>
            <Card className="shadow-lg">
              <CardHeader>
                <CardTitle className="text-red-700">AI Voiceover</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div>
                    <Label className="font-semibold mb-2 block">Language</Label>
                    <Select 
                      value={storyData.language} 
                      onValueChange={(value) => setStoryData(prev => ({ ...prev, language: value }))}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {languages.map(lang => (
                          <SelectItem key={lang.value} value={lang.value}>{lang.label}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  {audioUrl && (
                    <div className="bg-gray-50 p-4 rounded">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-semibold">Story Narration</span>
                        <span className="text-xs text-gray-500">2:34</span>
                      </div>
                      <audio controls src={audioUrl} className="w-full mb-2" />
                      <Button size="sm" className="w-full">
                        <Download className="w-4 h-4 mr-2" />Download MP3
                      </Button>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          </div>
          <div className="mt-8 text-center">
            <Button 
              size="lg" 
              onClick={() => setCurrentScreen('export')} 
              className="bg-gradient-to-r from-orange-600 to-red-600 hover:from-orange-700 hover:to-red-700"
            >
              <Share className="w-4 h-4 mr-2" />Continue to Export
            </Button>
          </div>
        </div>
      </div>
    </div>
  );

  const renderExportScreen = () => (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-orange-50">
      <div className="container mx-auto px-4 py-8">
        <div className="max-w-4xl mx-auto">
          <div className="mb-8">
            <h1 className="text-4xl font-bold text-gray-800 mb-2">Export & Share</h1>
            <p className="text-gray-600">Your story is ready</p>
          </div>
          <Card className="shadow-xl mb-8">
            <CardHeader>
              <CardTitle className="text-orange-700">Story Summary</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid md:grid-cols-2 gap-6">
                <div>
                  <h3 className="font-semibold text-lg mb-4">{generatedStory?.title ?? 'Untitled'}</h3>
                  <div className="space-y-2 text-sm">
                    <p><span className="font-semibold">Language:</span> {storyData.language || 'Not specified'}</p>
                    <p><span className="font-semibold">Scenes:</span> {generatedStory?.scenes.length || 0}</p>
                  </div>
                </div>
                <div>
                  <h4 className="font-semibold mb-2">Themes</h4>
                  <div className="flex flex-wrap gap-2">
                    {storyData.themes.map(theme => (
                      <Badge key={theme} variant="secondary">{theme}</Badge>
                    ))}
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
          <div className="grid md:grid-cols-2 gap-6">
            <Card className="shadow-lg">
              <CardHeader>
                <CardTitle>Share Your Story</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <Button className="w-full" variant="outline">
                  <Share className="w-4 h-4 mr-2" />Share via Email
                </Button>
                <Button className="w-full" variant="outline">
                  <Share className="w-4 h-4 mr-2" />Copy Link
                </Button>
                <Button className="w-full" variant="outline">
                  <Download className="w-4 h-4 mr-2" />Export ZIP
                </Button>
              </CardContent>
            </Card>
            <Card className="shadow-lg">
              <CardHeader>
                <CardTitle>Project Management</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <Button className="w-full">Save to Dashboard</Button>
                <Button 
                  className="w-full" 
                  variant="outline" 
                  onClick={() => setCurrentScreen('home')}
                >
                  <Home className="w-4 h-4 mr-2" />New Story
                </Button>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );

  const screens = {
    home: renderHomeScreen,
    builder: renderBuilderScreen,
    preview: renderPreviewScreen,
    script: renderScriptScreen,
    addons: renderAddonsScreen,
    export: renderExportScreen
  };

  return (
    <div className="relative font-sans">
      {screens[currentScreen]()}
      <div className="fixed top-4 right-4 z-50 space-y-2">
        {toasts.map(toast => (
          <div 
            key={toast.id} 
            className={`p-4 rounded-lg shadow-lg border max-w-sm ${
              toast.variant === 'destructive' 
                ? 'bg-red-50 border-red-200 text-red-800' 
                : 'bg-green-50 border-green-200 text-green-800'
            }`}
          >
            <div className="flex items-start justify-between">
              <div className="flex items-start space-x-2">
                {toast.variant === 'destructive' ? (
                  <AlertCircle className="w-5 h-5 mt-0.5 text-red-600" />
                ) : (
                  <CheckCircle className="w-5 h-5 mt-0.5 text-green-600" />
                )}
                <div>
                  <div className="font-semibold">{toast.title}</div>
                  {toast.description && (
                    <div className="text-sm mt-1">{toast.description}</div>
                  )}
                </div>
              </div>
              <button 
                onClick={() => setToasts(prev => prev.filter(t => t.id !== toast.id))} 
                className="ml-4 text-gray-400 hover:text-gray-600"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default Index;
