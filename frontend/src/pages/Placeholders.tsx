import { PlaceholderPage } from "@/components/PlaceholderPage";

export function ReviewPage() {
  return (
    <PlaceholderPage
      title="Review"
      description="Human review queue for AI drafts. Approve never posts to Reddit."
    />
  );
}

export function ProfilePage() {
  return (
    <PlaceholderPage
      title="Profile"
      description="Expertise, tone, constraints, and writing samples for AI drafting."
    />
  );
}

export function AnalyticsPage() {
  return (
    <PlaceholderPage
      title="Analytics"
      description="Discovery → relevance → draft → approval funnel."
    />
  );
}
