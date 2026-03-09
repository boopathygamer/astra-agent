# Build stage
FROM node:20-alpine AS build
WORKDIR /app
# Copy package files and install dependencies
COPY package*.json ./
RUN npm ci
# Copy source code and build
COPY . .
RUN npm run build

# Production serve stage using Nginx
FROM nginx:alpine
# Copy built assets
COPY --from=build /app/dist /usr/share/nginx/html
# Setup Nginx for Single Page Application routing
RUN echo 'server { \
    listen 80; \
    location / { \
        root /usr/share/nginx/html; \
        index index.html index.htm; \
        try_files $$uri $$uri/ /index.html; \
    } \
}' > /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
