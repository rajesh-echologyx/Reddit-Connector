type Props = {
  title: string;
  description: string;
};

export function PlaceholderPage({ title, description }: Props) {
  return (
    <section className="space-y-3">
      <h1
        className="text-3xl text-[var(--color-moss-deep)]"
        style={{ fontFamily: "var(--font-display)" }}
      >
        {title}
      </h1>
      <p className="max-w-2xl text-black/70">{description}</p>
      <p className="text-sm text-black/45">Coming in a later phase.</p>
    </section>
  );
}
