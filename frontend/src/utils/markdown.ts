import MarkdownIt from "markdown-it";

const markdown = new MarkdownIt({ html: false, breaks: true, linkify: true });

// Keep model-provided images from making unsolicited external requests.
markdown.renderer.rules.image = (tokens, index) =>
  markdown.utils.escapeHtml(tokens[index].content);
const defaultLink = markdown.renderer.rules.link_open;
markdown.renderer.rules.link_open = (tokens, index, options, env, renderer) => {
  tokens[index].attrSet("target", "_blank");
  tokens[index].attrSet("rel", "noopener noreferrer");
  tokens[index].attrSet("referrerpolicy", "no-referrer");
  return defaultLink
    ? defaultLink(tokens, index, options, env, renderer)
    : renderer.renderToken(tokens, index, options);
};

export function renderMarkdown(content: string): string {
  return markdown.render(content);
}
