import { copyFileSync, mkdirSync } from 'node:fs';

mkdirSync('app/static/vendor', { recursive: true });
for (const [src, dest] of [
  ['node_modules/bootstrap/dist/css/bootstrap.min.css', 'bootstrap.min.css'],
  ['node_modules/bootstrap/dist/js/bootstrap.bundle.min.js', 'bootstrap.bundle.min.js'],
  ['node_modules/htmx.org/dist/htmx.min.js', 'htmx.min.js'],
  ['node_modules/bootstrap/LICENSE', 'bootstrap.LICENSE'],
  ['node_modules/htmx.org/LICENSE', 'htmx.LICENSE'],
]) copyFileSync(src, `app/static/vendor/${dest}`);
