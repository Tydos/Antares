FROM node:20-alpine

WORKDIR /app

ENV CI=false

COPY package.json package-lock.json* ./
RUN npm ci

COPY . .

EXPOSE 3000

CMD ["npm", "start"]
