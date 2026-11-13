export default function Home() {
  return (
    <section className="space-y-6">
      <p className="font-mono text-xs uppercase tracking-[0.3em] text-accent-amber">
        Mission design game
      </p>
      <h1 className="text-5xl font-semibold tracking-tight">MISSIONFORGE</h1>
      <p className="max-w-2xl text-lg text-muted">
        Design a space mission, stress-test it against uncertainty, and fly it in a
        simulated mission control. All analysis runs in the Python engine; this
        interface only presents the results.
      </p>
    </section>
  );
}
