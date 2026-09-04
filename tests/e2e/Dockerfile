FROM mcr.microsoft.com/playwright:v1.55.0-noble

WORKDIR /workspace

COPY tests/e2e/package.json ./package.json
RUN npm install

COPY tests/e2e/playwright.config.ts ./playwright.config.ts
COPY tests/e2e/specs ./specs

CMD ["npx", "playwright", "test"]
