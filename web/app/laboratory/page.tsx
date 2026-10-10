import type { Metadata } from "next";
import Laboratory from "@/components/laboratory";

export const metadata: Metadata = {
  title: "Laboratory · ConjunctionTriage",
  description: "Change an encounter's geometry and uncertainty, compute collision probability, and inspect recorded or live agent reasoning.",
};

export default function LaboratoryPage() {
  return <Laboratory />;
}
