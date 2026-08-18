FROM node:20-alpine
WORKDIR /app
COPY package.json .
RUN npm install
COPY . .
ARG NEXT_PUBLIC_SDA_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_SDA_API_URL=$NEXT_PUBLIC_SDA_API_URL
RUN npm run build
CMD ["npm", "start"]
