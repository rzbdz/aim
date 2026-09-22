import { readFileSync } from 'node:fs'
const src = readFileSync('/root/tmp/agent-im/web/src/panes/OverviewPane.vue','utf8')
const body = /<script setup>([\s\S]*?)<\/script>/.exec(src)[1].split('\n').filter(l=>!/^\s*import\s/.test(l)).join('\n')
const computed=(fn)=>({get value(){return fn()}})
const stubs={computed,ref:(v)=>({value:v}),inject:()=>({service:()=>({})}),useBoard:()=>globalThis.__board,
 isPromise:()=>false,isOverdue:()=>false,PRIORITY_TYPE:{},STATUS_TYPE:{},RouterLink:{},PhaseApprovalCard:{},PromiseTag:{},TaskLink:{},days:()=>0,today:()=>'2026-09-22'}
const names=Object.keys(stubs)
const make=()=>new Function(...names,`${body}\nreturn { recentConversations, receiptGroups, threadKey }`)(...names.map(n=>stubs[n]))
const re=/^RECEIPT for\s+/
const rc=(ts,{from='codex',to='claude-session1'}={})=>({from,to,ts,subject:`RECEIPT for ${ts.replace(/[-:]/g,'')}-${to}`,msg_id:ts+'-r'})
const run=(label, rows, note='')=>{
  globalThis.__board={conversationRows:[...rows].sort((a,b)=>(a.ts<b.ts?-1:a.ts>b.ts?1:0))}
  const api=make(); const out=api.recentConversations.value
  console.log(label.padEnd(46), JSON.stringify(out.map(r=>r.receiptCount?`${r.receiptCount} arrived@${(r.ts||'').slice(11,19)}`:re.test(r.subject||'')?'raw:'+r.subject.slice(0,26):`row:${(r.subject||r.body||'').slice(0,20)}`)), note)
}
const ch=(ts,subject,id)=>({ts,subject,shape:'channel',channel:id,room:null})
const dm=(ts,subject)=>({ts,subject,shape:'direct',scope:'claude-session1 ⇄ codex'})
// 1. exact ts tie between two receipts of one pair
run('tie on ts, two receipts', [rc('2026-09-22T00:00:00.000Z'),rc('2026-09-22T00:00:00.000Z'),{ts:'2026-09-22T00:00:01.000Z',subject:'x',shape:'direct',scope:'a ⇄ b'}])
// 2. receipt with no ts
run('receipt with empty ts', [{...rc('2026-09-22T00:00:00.000Z'),ts:''},rc('2026-09-22T00:00:10.000Z'),{ts:'2026-09-22T00:00:20.000Z',subject:'x',shape:'direct',scope:'a ⇄ b'}])
// 3. receipt with no subject at all
run('receipt missing subject', [{...rc('2026-09-22T00:00:00.000Z'),subject:''},rc('2026-09-22T00:00:10.000Z'),{ts:'2026-09-22T00:00:20.000Z',subject:'x',shape:'direct',scope:'a ⇄ b'}])
// 4. two pairs whose directScope could collide: ['a','b ⇄ c'] vs ['a ⇄ b','c']
run('scope-collision pairs a/b⇄c and a⇄b/c',
  [ {ts:'2026-09-22T00:00:00.000Z',subject:'',shape:'direct',scope:['a','b ⇄ c'].map(String).sort().join(' ⇄ '),from:'a',to:'b ⇄ c'},
    {ts:'2026-09-22T00:00:00.500Z',subject:'',shape:'direct',scope:['a ⇄ b','c'].map(String).sort().join(' ⇄ '),from:'a ⇄ b',to:'c'},
    rc('2026-09-22T00:00:01.000Z'),rc('2026-09-22T00:00:02.000Z'),rc('2026-09-22T00:00:03.000Z') ])
// 5. a group whose newest receipt is OUTSIDE the window but older ones inside
run('newest receipt outside window, older inside',
  [rc('2026-09-22T00:00:00.000Z'),rc('2026-09-22T00:00:10.000Z'),rc('2026-09-22T00:00:20.000Z'),
   ...Array.from({length:4},(_,i)=>({ts:`2026-09-22T00:0${5+i}:00.000Z`,subject:`n${i}`,shape:'direct',scope:'a ⇄ b'})),
   rc('2026-09-22T00:09:00.000Z')])
// 6. six receipts of one group, no other rows at all
run('six receipts, nothing else', Array.from({length:6},(_,i)=>rc(`2026-09-22T00:0${i}:00.000Z`)))
// 7. same conversation in TWO shapes: channel receipt + direct receipt
run('receipt in a channel AND the direct pair',
  [ch('2026-09-22T00:00:00.000Z','RECEIPT for x-claude-session1','hello'),ch('2026-09-22T00:00:01.000Z','RECEIPT for y-claude-session1','hello'),ch('2026-09-22T00:00:02.000Z','RECEIPT for z-claude-session1','hello'),dm('2026-09-22T00:00:03.000Z','RECEIPT for w-claude-session1'),dm('2026-09-22T00:00:04.000Z','RECEIPT for v-claude-session1')])
// 8. one receipt only, in a full window
run('single receipt among ordinary rows',[rc('2026-09-22T00:00:00.000Z'),...Array.from({length:4},(_,i)=>({ts:`2026-09-22T00:0${i+1}:00.000Z`,subject:`n${i}`,shape:'direct',scope:'a ⇄ b'}))])
