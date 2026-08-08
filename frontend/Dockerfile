FROM node:20-alpine

WORKDIR /app

COPY package.json bun.lock* ./
RUN npm ci

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host"]
