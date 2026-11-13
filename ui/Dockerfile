# Page image: Next.js standalone server (port 3000).
# NEXT_PUBLIC_* values are inlined into the JavaScript at build time and are read by the
# BROWSER, so they must be an address the user's browser can reach (not a container name).
FROM node:22-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:22-slim AS build
ARG NEXT_PUBLIC_API_BASE=http://127.0.0.1:8000
ARG NEXT_PUBLIC_FIXTURES=0
ENV NEXT_PUBLIC_API_BASE=$NEXT_PUBLIC_API_BASE \
    NEXT_PUBLIC_FIXTURES=$NEXT_PUBLIC_FIXTURES \
    NEXT_TELEMETRY_DISABLED=1
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:22-slim AS runtime
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0
WORKDIR /app
COPY --from=build --chown=node:node /app/.next/standalone ./
COPY --from=build --chown=node:node /app/.next/static ./.next/static
USER node
EXPOSE 3000
CMD ["node", "server.js"]
