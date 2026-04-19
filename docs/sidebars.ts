import type {SidebarsConfig} from "@docusaurus/plugin-content-docs";

const sidebars: SidebarsConfig = {
  tutorialSidebar: [
    {
      type: "doc",
      id: "index",
      label: "Overview",
    },
    {
      type: "category",
      label: "Guides",
      items: [
        "guides/system-overview",
        "guides/development-guide",
      ],
    },
    {
      type: "category",
      label: "Reference",
      items: [
        "reference/scripts-reference",
      ],
    },
    {
      type: "category",
      label: "Design",
      items: [
        "design/dro-generation",
        "design/ro-generation",
        "design/rro-aro-generation",
        "design/dro-ro-transfer",
      ],
    },
    {
      type: "category",
      label: "Theory",
      items: [
        "theory/cr3bp-theory",
        "theory/differential-correction",
        "theory/continuation-method",
      ],
    },
    {
      type: "category",
      label: "Algorithms",
      items: [
        "algorithms/feasible-candidate-criteria",
        "algorithms/grid-search-trajectory-optimization",
      ],
    },
  ],
};

export default sidebars;
