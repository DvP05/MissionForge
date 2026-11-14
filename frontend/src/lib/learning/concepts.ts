/** Just-in-time concept cards, one per learning outcome (prod LO-1 ... LO-7). */
export interface Concept {
  id: "lo1" | "lo2" | "lo3" | "lo4" | "lo5" | "lo6" | "lo7";
  title: string;
  body: string;
}

export const CONCEPTS: Record<Concept["id"], Concept> = {
  lo1: {
    id: "lo1",
    title: "Why science objectives become measurable requirements",
    body: "A science question such as “what is it made of?” cannot be built or tested. Each objective is broken into measurements an instrument can make, so the design can be checked against them.",
  },
  lo2: {
    id: "lo2",
    title: "Constraints are coupled",
    body: "Swapping one part moves several budgets at once: a bigger radio adds mass and power, which can push the launch mass and the battery margin. Watch which other constraints change when you edit one subsystem.",
  },
  lo3: {
    id: "lo3",
    title: "Mass, power and energy are different budgets",
    body: "Mass is what the rocket must lift. Power (watts) is how much the spacecraft draws at one moment. Energy (watt-hours) is power over time: a short high-power burst can fit the power limit and still drain the battery.",
  },
  lo4: {
    id: "lo4",
    title: "C3 is not the spacecraft's delta-v",
    body: "C3 is the launch energy the rocket gives the spacecraft to escape Earth. Delta-v is what the spacecraft's own thrusters must still provide later, for example to match the asteroid's speed. They come from different budgets.",
  },
  lo5: {
    id: "lo5",
    title: "Collected is not returned",
    body: "Science only counts once it reaches Earth. Data collected on board waits in storage for a ground pass; if the link is weak or storage fills first, collected data never comes back.",
  },
  lo6: {
    id: "lo6",
    title: "Margins buy robustness",
    body: "Every number has uncertainty. A design that just meets its limits fails when reality is slightly worse; margin is what lets it survive the spread. The robustness lab shows how often a design stays feasible.",
  },
  lo7: {
    id: "lo7",
    title: "Operations choices trade one goal for another",
    body: "Protecting the spacecraft (safe mode, holding an observation) can cost science, while pressing on keeps science at a risk. Out of contact, the onboard policy makes these choices from rules set in advance.",
  },
};
