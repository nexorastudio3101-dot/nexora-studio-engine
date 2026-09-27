FROM node:22-alpine
RUN apk add --no-cache ffmpeg
WORKDIR /app
COPY package.json ./
COPY src ./src
COPY public ./public
EXPOSE 10000
CMD ["node","src/server.mjs"]
