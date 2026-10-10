import type { Metadata } from "next";
import Observatory from "@/components/observatory";

export const metadata: Metadata = {
  title: "The Observatory",
  description: "Explore 2,000 benchmark satellite encounters in three dimensions, inspect their uncertainty, and understand what collision probability can and cannot tell you.",
};

export default function ObservatoryPage() {
  return <Observatory />;
}
