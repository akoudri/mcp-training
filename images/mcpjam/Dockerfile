# Client graphique MCPJam Inspector, version épinglée (voir docs/decisions/mcpjam.md).
# Paquet npm publié par l'amont (dist/ déjà construit) : même binaire que
# `npx @mcpjam/inspector@3.12.0`, sans reconstruire le monorepo ni Chromium.
ARG NODE_VERSION=24.14.0
FROM node:${NODE_VERSION}-bookworm-slim
ARG MCPJAM_VERSION=3.12.0
ENV NODE_ENV=production \
    DOCKER_CONTAINER=true \
    PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 \
    MCPJAM_INSPECTOR_SUPPRESS_AUTO_OPEN=1
RUN npm install -g --omit=dev @mcpjam/inspector@${MCPJAM_VERSION} && npm cache clean --force
USER node
WORKDIR /home/node
EXPOSE 6274
ENTRYPOINT ["inspector"]
CMD ["--config", "/config/client.config.json"]
