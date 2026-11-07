# Answer me with HTML

`am.mjs` is the generated CLI from [Answer me with HTML v0.5.10](https://github.com/QingYunA/answer-me-with-html/tree/f82dd6dce3ca95b0e565f8cffaf5eba23f4c995f). The local bundle changes the project name and both GitHub links in the page credit. The integrity test reverses those two source edits and checks the result against the original upstream SHA-256, `5e08fda8e976927b16596624cf605e5aadd77828ee690a412b5a9a96584d4f2c`.

The skill calls this bundle through `scripts/render_html.mjs`; no separate page skill is needed. The wrapper disables the upstream update check, hides the toolbar, preserves the original page styles, and supports a plain-text `--footer` override. It reapplies those options after a panel patch and includes the license notices in the HTML. The default project credit still comes from this bundle. To update the renderer, replace the bundle and accompanying notices from a pinned upstream release, reapply the page credit in `colophon`, and rerun the rendering and installation checks.

- [Answer me with HTML](LICENSE)
- [marked 18.0.14](licenses/marked.txt)
- [@dagrejs/dagre 3.1.1](licenses/dagre.txt)
- [@dagrejs/graphlib 4.0.5](licenses/graphlib.txt)
- [Temml 0.14.0](licenses/temml.txt)
- [Bangers](licenses/OFL-Bangers.txt)
