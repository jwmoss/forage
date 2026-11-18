# Reduce startup time for local commands

A warm-filesystem benchmark launched nine fresh Python processes per case. The median for `forage --version` through the source entry point was 205 ms. The same interpreter took 21.5 ms to launch and exit.

`src/forage/cli.py` imports browser authentication, Playwright, scraper code, and result models while registering commands. An import trace confirmed that all four load before the version callback runs.

- [ ] Defer browser and model imports to commands that need them.
- [ ] Measure version, help, and a local export with the same interpreter.
- [ ] Check group scraping and Marketplace reads with the deployed selectors and session before shipping. Keep browser navigation and collection limits intact.
