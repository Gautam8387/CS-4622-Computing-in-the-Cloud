
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Download, CheckCircle, XCircle } from "lucide-react";
import { Button } from "./ui/button";

interface HistoryItem {
  id: string;
  filename: string;
  inputFormat: string;
  outputFormat: string;
  status: "completed" | "failed";
  timestamp: string;
}

const mockHistory: HistoryItem[] = [
  {
    id: "1",
    filename: "presentation.mov",
    inputFormat: "MOV",
    outputFormat: "MP4",
    status: "completed",
    timestamp: "2024-03-10 14:30",
  },
  {
    id: "2",
    filename: "podcast.wav",
    inputFormat: "WAV",
    outputFormat: "MP3",
    status: "completed",
    timestamp: "2024-03-10 14:15",
  },
  {
    id: "3",
    filename: "recording.mkv",
    inputFormat: "MKV",
    outputFormat: "MP4",
    status: "failed",
    timestamp: "2024-03-10 14:00",
  },
];

export function TranscodingHistory() {
  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Filename</TableHead>
            <TableHead>Input Format</TableHead>
            <TableHead>Output Format</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Timestamp</TableHead>
            <TableHead>Action</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {mockHistory.map((item) => (
            <TableRow key={item.id}>
              <TableCell className="font-medium">{item.filename}</TableCell>
              <TableCell>{item.inputFormat}</TableCell>
              <TableCell>{item.outputFormat}</TableCell>
              <TableCell>
                {item.status === "completed" ? (
                  <div className="flex items-center space-x-2 text-green-600">
                    <CheckCircle className="h-4 w-4" />
                    <span>Completed</span>
                  </div>
                ) : (
                  <div className="flex items-center space-x-2 text-red-600">
                    <XCircle className="h-4 w-4" />
                    <span>Failed</span>
                  </div>
                )}
              </TableCell>
              <TableCell>{item.timestamp}</TableCell>
              <TableCell>
                {item.status === "completed" && (
                  <Button variant="ghost" size="sm">
                    <Download className="h-4 w-4" />
                  </Button>
                )}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
