import React, { useState } from "react";
import { generateStory, generateVoiceover } from "../../api/story";
import { Button } from "../ui/button";

const StoryGenerator = () => {
  const [prompt, setPrompt] = useState("");
  const [story, setStory] = useState<any>(null);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleGenerate = async () => {
    setLoading(true);
    setAudioUrl(null);
    try {
      const storyRes = await generateStory({
        prompt,
        genre: "Drama",
        length_minutes: 5,
        language: "English",
        themes: [],
        use_real_world_context: true,
      });

      setStory(storyRes);

      const voiceText = storyRes.scenes
        .map(
          (s: any) =>
            `${s.narration} ${s.dialogues.join(" ")}`
        )
        .join(" ");

      const audioBlob = await generateVoiceover(voiceText);
      setAudioUrl(URL.createObjectURL(audioBlob));
    } catch (err) {
      console.error(err);
      alert("Something went wrong!");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4 p-4">
      <textarea
        className="w-full p-2 border rounded"
        placeholder="Enter your cinematic prompt..."
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
      />
      <Button onClick={handleGenerate} disabled={loading}>
        {loading ? "Generating..." : "Generate Story"}
      </Button>

      {story && (
        <div className="mt-6 space-y-4">
          <h2 className="text-xl font-bold">{story.title}</h2>
          <p className="italic">Genre: {story.genre}</p>
          <p>Length: {story.length_minutes} minutes</p>

          <div className="mt-4">
            <h3 className="font-semibold">Characters:</h3>
            <ul className="list-disc ml-5">
              {story.characters?.map((char: any, idx: number) => (
                <li key={idx}>
                  <strong>{char.name}:</strong> {char.bio}
                </li>
              ))}
            </ul>
          </div>

          <div className="mt-4 space-y-3">
            <h3 className="font-semibold">Scenes:</h3>
            {story.scenes?.map((scene: any, index: number) => (
              <div key={index} className="border p-3 rounded">
                <h4 className="font-bold">
                  Scene {index + 1}: {scene.title}
                </h4>
                <p>
                  <strong>Narration:</strong> {scene.narration}
                </p>
                <div>
                  <strong>Dialogues:</strong>
                  <ul className="list-disc ml-5">
                    {scene.dialogues.map(
                      (line: string, idx: number) => (
                        <li key={idx}>{line}</li>
                      )
                    )}
                  </ul>
                </div>
              </div>
            ))}
          </div>

          {story.source_facts?.length > 0 && (
            <div className="mt-4">
              <h3 className="font-semibold">Source Facts:</h3>
              <ul className="list-disc ml-5">
                {story.source_facts.map(
                  (fact: string, idx: number) => (
                    <li key={idx}>{fact}</li>
                  )
                )}
              </ul>
            </div>
          )}
        </div>
      )}

      {audioUrl && (
        <div className="mt-6">
          <audio controls src={audioUrl} />
        </div>
      )}
    </div>
  );
};

export default StoryGenerator;
