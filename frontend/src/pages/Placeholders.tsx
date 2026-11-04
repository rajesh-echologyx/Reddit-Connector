import { PlaceholderPage } from "@/components/PlaceholderPage";

export function ReviewPage() {
  return (
    <PlaceholderPage
      title="Review"
      description="Human review queue for AI drafts. Approve never posts to Reddit."
    />
  );
}

export function PostsPage() {
  return (
    <PlaceholderPage
      title="Posts"
      description="Discovered Reddit posts and relevance scores."
    />
  );
}

export function MonitorsPage() {
  return (
    <PlaceholderPage
      title="Monitors"
      description="Keyword and subreddit monitors that poll via the official Reddit API."
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

export function SettingsPage() {
  return (
    <PlaceholderPage
      title="Settings"
      description="Reddit OAuth connection, feature flags, and operator preferences."
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
