FROM mcr.microsoft.com/playwright:v1.55.0-noble

WORKDIR /workspace

COPY tests/e2e/package.json ./package.json
RUN npm install

COPY tests/e2e/playwright.config.js ./playwright.config.js
COPY tests/e2e/specs ./specs

CMD ["npx", "playwright", "test"]
