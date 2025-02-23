
import { useState, useCallback } from "react";
import { useDropzone } from "@uploadthing/react";
import { cn } from "@/lib/utils";
import { Cloud, FileSymlink, Loader2 } from "lucide-react";
import { Button } from "./ui/button";
import { Progress } from "./ui/progress";

interface DropZoneProps {
  className?: string;
  loading?: boolean;
  onFilesAdded?: (files: File[]) => void;
}

export function DropZone({ className, loading, onFilesAdded }: DropZoneProps) {
  const [draggedFiles, setDraggedFiles] = useState<File[]>([]);
  const [progress, setProgress] = useState(0);

  const onDrop = useCallback(
    (acceptedFiles: File[]) => {
      setDraggedFiles(acceptedFiles);
      if (onFilesAdded) {
        onFilesAdded(acceptedFiles);
      }
      // Simulate upload progress
      let currentProgress = 0;
      const interval = setInterval(() => {
        currentProgress += 5;
        setProgress(currentProgress);
        if (currentProgress >= 100) {
          clearInterval(interval);
        }
      }, 100);
    },
    [onFilesAdded]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    multiple: true,
  });

  return (
    <div
      {...getRootProps()}
      className={cn(
        "relative rounded-lg border border-dashed p-8 transition-colors hover:bg-muted/50",
        isDragActive ? "bg-muted" : "bg-transparent",
        className
      )}
    >
      <div className="flex flex-col items-center justify-center space-y-4 text-center">
        <div className="flex items-center justify-center space-x-4">
          <Cloud className="h-8 w-8 text-muted-foreground" />
          <FileSymlink className="h-8 w-8 text-muted-foreground" />
        </div>
        <div className="flex flex-col space-y-1">
          <p className="text-lg font-medium">Drag & drop your files here</p>
          <p className="text-sm text-muted-foreground">
            or click to select files for transcoding
          </p>
        </div>
        {loading ? (
          <div className="flex items-center justify-center space-x-2">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            <p className="text-sm text-muted-foreground">Processing...</p>
          </div>
        ) : (
          <Button size="sm" variant="secondary">
            Select Files
          </Button>
        )}
        <input {...getInputProps()} />
      </div>
      {draggedFiles.length > 0 && (
        <div className="mt-4 space-y-3">
          {draggedFiles.map((file, index) => (
            <div key={index} className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="font-medium">{file.name}</span>
                <span className="text-muted-foreground">
                  {(file.size / 1024 / 1024).toFixed(2)} MB
                </span>
              </div>
              <Progress value={progress} className="h-1" />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
