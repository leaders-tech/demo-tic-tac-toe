# This file builds the production frontend image for Docker and Dokploy.
# Edit this file when frontend build steps, nginx runtime setup, or container ports change.
# Copy a stage pattern here when you add another small static frontend image.
FROM node:25.6-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

ARG VITE_BACKEND_URL
ENV VITE_BACKEND_URL=${VITE_BACKEND_URL}

RUN npm run build

FROM nginx:1.29.5-alpine-slim AS runtime

COPY nginx.conf /etc/nginx/nginx.conf
COPY --from=builder /app/dist /usr/share/nginx/html

RUN mkdir -p /tmp/nginx /var/cache/nginx && \
    chown -R nginx:nginx /tmp/nginx /var/cache/nginx /usr/share/nginx/html

USER nginx

EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]
