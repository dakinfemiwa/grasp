import { BookOpen, ChevronRight } from "lucide-react";
import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { cn } from "@/lib/utils";

const families = [
  { title: "Quadratic models", detail: "Rectangle dimensions from an area", spec: "2.3" },
  { title: "Straight-line models", detail: "Two data points, prediction, reliability", spec: "3.1" },
  { title: "Trigonometric models", detail: "Height of a point on a rotating wheel", spec: "5.9" },
];

export function PracticePanel() {
  return (
    <Card id="practice" className="mt-8 border-cyan-300/20 bg-slate-900/80">
      <CardHeader>
        <div className="flex items-center justify-between gap-4">
          <div>
            <CardTitle>Practice</CardTitle>
            <CardDescription className="mt-1">
              Pure mathematics modelling, without calculus. Spec references are
              to Edexcel A level Mathematics (9MA0).
            </CardDescription>
          </div>
          <BookOpen className="size-5 text-cyan-300" />
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <ul className="grid gap-3 sm:grid-cols-3">
          {families.map((f) => (
            <li key={f.title} className="rounded-lg border border-slate-800 px-4 py-3">
              <p className="text-sm font-medium text-slate-200">{f.title}</p>
              <p className="mt-1 text-xs text-slate-500">
                {f.detail} · spec {f.spec}
              </p>
            </li>
          ))}
        </ul>
        <Link href="/practice" className={cn(buttonVariants({ size: "sm" }))}>
          Start practising <ChevronRight className="size-4" />
        </Link>
      </CardContent>
    </Card>
  );
}
