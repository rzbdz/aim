import { chromium } from 'playwright'
const BASE='http://127.0.0.1:8777'
const b=await chromium.launch(); const p=await b.newPage({viewport:{width:1440,height:1000}})
const warn=[]; p.on('console', m=>{ if(['warning','error'].includes(m.type())) warn.push(m.type()+': '+m.text().slice(0,200)) })
await p.goto(BASE+'/#/barrier',{waitUntil:'networkidle'}); await p.waitForTimeout(1200)
const dump=async(label)=>{
  const r=await p.evaluate(()=>{
    const vis=e=>e.getBoundingClientRect().height>0
    const cards=[...document.querySelectorAll('.el-card')].filter(vis)
    const refCard=cards.find(c=>/refusals —/.test(c.innerText))
    const inputs=[...document.querySelectorAll('.el-input__inner')].filter(vis).map(i=>({ph:i.placeholder, v:i.value}))
    const sels=[...document.querySelectorAll('.el-select')].filter(vis).map(s=>s.innerText.replace(/\s+/g,' ').trim().slice(0,30))
    return { search: location.search, hash: location.hash,
      header: refCard? refCard.innerText.split('\n').slice(0,3).join(' | ') : null,
      refRows: refCard? refCard.querySelectorAll('tbody tr').length : null,
      empty: refCard? refCard.innerText.match(/no refusal[^\n]*/)?.[0] : null,
      inputs, sels }
  })
  console.log(label, JSON.stringify(r))
}
await dump('DEFAULT(barrier-v0)')
for (const t of ['#hello','#dev','#barrier-v0']) {
  await p.locator('.el-tabs__item',{hasText:t}).first().click(); await p.waitForTimeout(900)
  await dump('TAB '+t)
}
// does the tab click survive a reload?
console.log('WARNINGS', JSON.stringify(warn.slice(0,6)))
await b.close()
