# Capital Insight frontend: Next.js standalone server.
# Runtime configuration (DATA_SOURCE, BACKEND_API_URL) is read on the server at request time,
# so one image works against any core API. Never bake secrets into this image.

FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

FROM node:22-alpine AS build
WORKDIR /app
# Pages without request-time APIs are prerendered during `next build`, so the data source
# must match runtime here too (otherwise e.g. /sign-in is frozen in demo mode).
# These are non-secret settings; the backend is not contacted during the build.
ARG DATA_SOURCE=http
ARG BACKEND_API_URL=http://api:8000
ENV NEXT_TELEMETRY_DISABLED=1 NEXT_OUTPUT=standalone DATA_SOURCE=$DATA_SOURCE BACKEND_API_URL=$BACKEND_API_URL
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:22-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 HOSTNAME=0.0.0.0 PORT=3000
RUN addgroup -S -g 1001 nodejs && adduser -S -u 1001 -G nodejs nextjs
COPY --from=build --chown=nextjs:nodejs /app/public ./public
COPY --from=build --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=build --chown=nextjs:nodejs /app/.next/static ./.next/static
USER nextjs
EXPOSE 3000
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s CMD node -e "fetch('http://127.0.0.1:3000/sign-in').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"
CMD ["node", "server.js"]
