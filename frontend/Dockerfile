FROM node:18-alpine AS build

WORKDIR /app

# copy package files and install dependencies
COPY package*.json ./
RUN npm ci --no-audit --no-fund

# copy source and build
COPY . .
RUN npm run build

FROM nginx:stable-alpine

# remove default nginx content
RUN rm -rf /usr/share/nginx/html/*

# copy built static assets from builder
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
