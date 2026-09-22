import { chromium } from 'playwright'
const BASE='http://127.0.0.1:8777'
const b=await chromium.launch(); const p=await b.newPage({viewport:{width:1440,height:1000}})
// can the URL alone reach the hello refusals?
await p.goto(BASE+'/#/barrier?channel=hello',{waitUntil:'networkidle'}); await p.waitForTimeout(1400)
const r=await p.evaluate(()=>{
  const vis=e=>e.getBoundingClientRect().height>0
  const card=[...document.querySelectorAll('.el-card')].filter(vis).find(c=>/refusals —/.test(c.innerText))
  return { hash:location.hash, header: card.innerText.split('\n')[0],
    rows: card.querySelectorAll('tbody tr').length,
    firstRow: card.querySelectorAll('tbody tr')[0]?.innerText.replace(/\s+/g,' ').slice(0,110) }
})
console.log('URL-ONLY #/barrier?channel=hello ->', JSON.stringify(r))
// Help: the prefixes table and the glossary terms
await p.goto(BASE+'/#/help',{waitUntil:'networkidle'}); await p.waitForTimeout(1200)
const h=await p.evaluate(()=>{
  const tabs=[...document.querySelectorAll('table')].map(t=>({
    head:[...t.querySelectorAll('thead th')].map(x=>x.innerText.trim()),
    rows:[...t.querySelectorAll('tbody tr')].map(r=>r.innerText.replace(/\s+/g,' ').trim().slice(0,90))}))
  return tabs
})
h.forEach((t,i)=>{ console.log('TABLE'+i, JSON.stringify(t.head)); t.rows.forEach(r=>console.log('   ', r)) })
await b.close()
