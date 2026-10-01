# Servicio frontend de docker-compose.yml: monta ./frontend en /app, deja node_modules en un
# volumen propio y arranca con `npm run dev -- --host` en el puerto 5173.
# Node 22: Vite 8 necesita Node ^20.19 o >=22.12.
FROM node:22-alpine
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-fund --no-audit
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host"]
