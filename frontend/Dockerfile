# BoloBank web image: builds the React app, serves it with nginx, and
# forwards /api to the API containers.
#   docker build -t bolobank-web --build-arg VITE_GOOGLE_CLIENT_ID=... ./frontend
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# Public value (sent to browsers); only needed if Google staff sign-in is used.
ARG VITE_GOOGLE_CLIENT_ID=""
ENV VITE_GOOGLE_CLIENT_ID=$VITE_GOOGLE_CLIENT_ID
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
