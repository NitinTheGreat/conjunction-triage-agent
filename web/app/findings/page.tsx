import type { Metadata } from "next";
import FindingsPage from "@/components/findings";

export const metadata: Metadata = {
  title: "The findings",
  description: "How reuse of the same tracking observations across conjunction messages degrades history-based risk forecasts: a controlled simulation with a frozen confirmatory test, and the retrospective real-data analysis.",
};

export default function Findings() {
  return <FindingsPage />;
}
