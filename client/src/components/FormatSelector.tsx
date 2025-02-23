
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface FormatSelectorProps {
  type: "input" | "output";
  onChange: (value: string) => void;
}

export function FormatSelector({ type, onChange }: FormatSelectorProps) {
  const formats = {
    video: ["MP4", "AVI", "MOV", "MKV", "WebM"],
    audio: ["MP3", "WAV", "FLAC", "AAC", "OGG"],
  };

  return (
    <Select onValueChange={onChange}>
      <SelectTrigger className="w-full">
        <SelectValue placeholder={`Select ${type} format`} />
      </SelectTrigger>
      <SelectContent>
        <SelectGroup>
          <SelectLabel>Video Formats</SelectLabel>
          {formats.video.map((format) => (
            <SelectItem key={format} value={format.toLowerCase()}>
              {format}
            </SelectItem>
          ))}
        </SelectGroup>
        <SelectGroup>
          <SelectLabel>Audio Formats</SelectLabel>
          {formats.audio.map((format) => (
            <SelectItem key={format} value={format.toLowerCase()}>
              {format}
            </SelectItem>
          ))}
        </SelectGroup>
      </SelectContent>
    </Select>
  );
}
