import { BookOpen } from "lucide-react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

// Placeholder while practice moves from Convex to the FastAPI backend (Stage 7).
export function PracticePanel() {
  return (
    <Card id="practice" className="mt-8 border-cyan-300/20 bg-slate-900/80">
      <CardHeader>
        <div className="flex items-center justify-between gap-4">
          <div>
            <CardTitle>Practice</CardTitle>
            <CardDescription className="mt-1">
              Adaptive practice is being connected to the new backend.
            </CardDescription>
          </div>
          <BookOpen className="size-5 text-cyan-300" />
        </div>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-slate-500">
          Questions will appear here once the question bank is live.
        </p>
      </CardContent>
    </Card>
  );
}
