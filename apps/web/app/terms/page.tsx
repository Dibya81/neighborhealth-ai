import { LegalPage, TERMS } from "@/components/legal";

export const metadata = { title: "Terms of use" };

export default function Terms() {
  return <LegalPage {...TERMS} />;
}
