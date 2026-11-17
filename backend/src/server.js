import { createApp } from "./app.js";

// PORT=0 picks a free port; the engines' test suites rely on this and parse
// the "listening on" line below, so keep its format stable.
const PORT = process.env.PORT ?? 4000;

const server = createApp().listen(PORT, "127.0.0.1", () => {
  console.log(`Upload harness listening on http://127.0.0.1:${server.address().port}`);
});
