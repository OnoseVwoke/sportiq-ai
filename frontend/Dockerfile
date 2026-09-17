FROM node:20-alpine

WORKDIR /app

COPY package.json ./
RUN npm install

COPY . .

# Vite bakes environment variables into the built JS at build time,
# not at container start time — so this has to be a build ARG, not
# a runtime "environment:" setting in docker-compose.yml.
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL

RUN npm run build

EXPOSE 3000
CMD ["npm", "run", "preview"]