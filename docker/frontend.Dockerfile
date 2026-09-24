# syntax=docker/dockerfile:1

FROM node:22-alpine AS base

WORKDIR /app

COPY frontend/package.json frontend/package-lock.json* /app/
RUN npm install

COPY frontend /app

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

# ---------------------------------------------------------------------------
# Production build stage (used via `docker build --target production`)
# ---------------------------------------------------------------------------
FROM base AS build
RUN npm run build

FROM nginx:1.27-alpine AS production
COPY --from=build /app/dist /usr/share/nginx/html
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
