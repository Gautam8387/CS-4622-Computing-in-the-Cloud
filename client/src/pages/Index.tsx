
import { useState } from "react";
import { DropZone } from "@/components/DropZone";
import { FormatSelector } from "@/components/FormatSelector";
import { TranscodingHistory } from "@/components/TranscodingHistory";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useToast } from "@/components/ui/use-toast";

export default function Index() {
  const [outputFormat, setOutputFormat] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const { toast } = useToast();

  const handleFilesAdded = async (files: File[]) => {
    if (!outputFormat) {
      toast({
        title: "Please select an output format",
        description: "Choose the desired output format before uploading files.",
        variant: "destructive",
      });
      return;
    }

    setLoading(true);
    // Simulate processing delay
    await new Promise((resolve) => setTimeout(resolve, 3000));
    setLoading(false);

    toast({
      title: "Files added successfully",
      description: `Added ${files.length} files for transcoding to ${outputFormat.toUpperCase()}`,
    });
  };

  return (
    <div className="min-h-screen bg-background p-6 animate-fade-up">
      <div className="mx-auto max-w-6xl space-y-8">
        <div className="space-y-2 text-center">
          <h1 className="text-4xl font-bold tracking-tighter sm:text-5xl md:text-6xl">
            Media Transcoding Service
          </h1>
          <p className="mx-auto max-w-[700px] text-gray-500 md:text-lg">
            Convert your media files to any format. Fast, secure, and reliable.
          </p>
        </div>

        <Card className="p-6 space-y-6">
          <div className="grid gap-6 md:grid-cols-2">
            <div className="space-y-2">
              <label className="text-sm font-medium">Output Format</label>
              <FormatSelector type="output" onChange={setOutputFormat} />
            </div>
          </div>

          <DropZone
            className="w-full"
            loading={loading}
            onFilesAdded={handleFilesAdded}
          />

          <div className="flex justify-end">
            <Button
              disabled={loading || !outputFormat}
              onClick={() => {
                toast({
                  title: "Starting transcoding process",
                  description: "Your files will be processed shortly.",
                });
              }}
            >
              Start Transcoding
            </Button>
          </div>
        </Card>

        <div className="space-y-4">
          <h2 className="text-2xl font-bold tracking-tight">Recent Transcoding Jobs</h2>
          <TranscodingHistory />
        </div>
      </div>
    </div>
  );
}
