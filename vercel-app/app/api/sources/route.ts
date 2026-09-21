export const runtime='nodejs';
export const dynamic='force-dynamic';

const sources=[{source_id:'asteria_federal',url:'https://asterian-federal-wage-site.vercel.app/'},{source_id:'bellwether_state',url:'https://bellwether-state-wage-site.vercel.app/'}];
export async function GET(){const results=await Promise.all(sources.map(async s=>{try{const r=await fetch(s.url,{redirect:'manual',headers:{'User-Agent':'AtlasCompliancePrototype/1.0'},signal:AbortSignal.timeout(20000)});if(!r.ok)throw new Error(`Source returned HTTP ${r.status}`);const html=await r.text();if(html.length>300000)throw new Error('Unexpectedly large source page');return{...s,html,fetched_at:new Date().toISOString()};}catch(e){return{...s,error:'Source could not be retrieved. Retry later; the last successful snapshot is preserved.'};}}));return Response.json({sources:results},{headers:{'Cache-Control':'no-store'}});}
