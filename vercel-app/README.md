# Atlas Compliance — Vercel application

This is the Vercel-native deployment of the Atlas assessment prototype.

- Standard Next.js application and API route
- Deterministic Python compliance engine executed in the browser with pinned
  Pyodide 0.27.7 CDN assets
- Browser-local, versioned demo workspace persistence
- Server-side source retrieval restricted to the two configured assessment URLs
- No real employee data, secrets, or production payroll decisions

## Local verification

```sh
npm install
npm run build
npm run dev
```

For Vercel, import the repository and set **Root Directory** to `vercel-app`.
No environment variables are required.

Browser storage is intentionally used for this public assessment deployment.
Export evidence before clearing site data or switching browsers.
