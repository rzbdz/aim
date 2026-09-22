import { readFileSync } from 'node:fs'
const src = readFileSync('/root/tmp/agent-im/web/src/panes/OverviewPane.vue','utf8')
const body = /<script setup>([\s\S]*?)<\/script>/.exec(src)[1].split('\n').filter(l=>!/^\s*import\s/.test(l)).join('\n')
const computed=(fn)=>({get value(){return fn()}})
const stubs={computed,ref:(v)=>({value:v}),inject:()=>({service:()=>({})}),useBoard:()=>globalThis.__board,
 isPromise:()=>false,isOverdue:()=>false,PRIORITY_TYPE:{},STATUS_TYPE:{},RouterLink:{},PhaseApprovalCard:{},PromiseTag:{},TaskLink:{},days:()=>0,today:()=>'2026-09-22'}
const names=Object.keys(stubs)
const build=()=>new Function(...names,`${body}\nreturn { recentConversations }`)(...names.map(n=>stubs[n]))
const stamp=(ts)=>ts.replace(/[-:]/g,'')
const receipt=(ts)=>({from:'codex',to:'claude-session1',ts,subject:`RECEIPT for ${stamp(ts)}-claude-session1`,msg_id:stamp(ts)+'-r',ack_required:false,acked_at:''})
const note=(ts,i)=>({from:'claude-session1',to:'codex',ts,subject:`routine note ${i}`,msg_id:stamp(ts)+'-n'+i,ack_required:false,acked_at:''})
const BURST=['2026-09-22T00:00:00.000Z','2026-09-22T00:00:30.000Z','2026-09-22T00:01:00.000Z','2026-09-22T00:01:30.000Z','2026-09-22T00:02:00.000Z','2026-09-22T00:02:30.000Z','2026-09-22T00:03:00.000Z'].map(receipt)
const tail=(n)=>Array.from({length:n},(_,i)=>note(`2026-09-22T00:${String(10+i).padStart(2,'0')}:00.000Z`,100+i))
for (const [name,mail] of [['BURST_ONLY',[...BURST]],['PLUS_TWO',[...BURST,...tail(2)]],['PLUS_FOUR',[...BURST,...tail(4)]]]) {
  globalThis.__board={conversationRows:mail.map(m=>({...m,shape:'direct',scope:'claude-session1 ⇄ codex'})).sort((a,b)=>(a.ts<b.ts?-1:a.ts>b.ts?1:0))}
  const out=build().recentConversations.value
  console.log(`${name.padEnd(11)} mail ${mail.length} | card-t0182 spec asserts toHaveCount(${Math.min(5,mail.length)}) | new code draws ${out.length} | subjects ${JSON.stringify(out.map(r=>r.receiptCount?`${r.receiptCount} arrived`:r.subject.slice(0,18)))}`)
}
