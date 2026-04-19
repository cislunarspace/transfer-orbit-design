import {type Config} from "@docusaurus/types";
import type * as Preset from "@docusaurus/preset-classic";

const config: Config = {
  title: "Transfer Orbit Design",
  tagline: "DRO to RO Two-Impulse Transfer",
  favicon: "img/favicon.ico",
  url: "https://ouyangjiahong.github.io",
  baseUrl: "/transfer-orbit-design/",
  organizationName: "ouyangjiahong",
  projectName: "transfer-orbit-design",
  onBrokenLinks: "warn",
  onBrokenMarkdownLinks: "warn",
  trailingSlash: false,

  i18n: {
    defaultLocale: "en",
    locales: ["en"],
  },

  markdown: {
    mermaid: true,
  },

  presets: [
    [
      "classic",
      {
        docs: {
          path: ".",
          sidebarPath: "./sidebars.ts",
          editUrl: "https://github.com/ouyangjiahong/transfer-orbit-design/edit/master/",
        },
        blog: false,
        theme: {
          customCss: "./src/css/custom.css",
        },
      } satisfies Preset.Options,
    ],
  ],

  themeConfig: {
    image: "img/social-card.jpg",
    navbar: {
      title: "Transfer Orbit Design",
      style: "dark",
      items: [
        {
          type: "docSidebar",
          sidebarId: "tutorialSidebar",
          position: "left",
          label: "Docs",
        },
        {
          href: "https://github.com/ouyangjiahong/transfer-orbit-design",
          label: "GitHub",
          position: "right",
        },
      ],
    },
    footer: {
      style: "dark",
      copyright: `© ${new Date().getFullYear()} Transfer Orbit Design. Built with Docusaurus.`,
    },
    prism: {
      theme: require("prism-react-renderer").githubDarkTheme,
      darkTheme: require("prism-react-renderer").githubDarkTheme,
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
