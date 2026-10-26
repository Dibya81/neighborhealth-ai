import { LegalPage, PRIVACY } from "@/components/legal";

export const metadata = { title: "Privacy notice" };

export default function Privacy() {
  return <LegalPage {...PRIVACY} />;
}
