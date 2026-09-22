import { chromium } from 'playwright'
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1440, height: 1000 } })
p.on('pageerror', e => console.log('PAGEERROR', e.message))
const sent = []
await p.route('**/api/command', async (route) => {
  const body = route.request().postDataJSON()
  sent.push(body.argv)
  await route.fulfill({ status: 200, contentType: 'application/json',
    body: JSON.stringify({ ok: true, rc: 0, argv: body.argv, stdout: 'stubbed: not actually run', stderr: '' }) })
})
await p.goto('http://127.0.0.1:8777/#/attention', { waitUntil: 'networkidle' })
await p.waitForTimeout(1000)

const survey = await p.evaluate(() => {
  const cards = [...document.querySelectorAll('.aim-phase-request')].map(c => ({
    text: c.innerText.replace(/\s+/g, ' ').slice(0, 120),
    buttons: [...c.querySelectorAll('button')].map(b => ({ label: b.innerText.trim(), disabled: b.disabled })),
  }))
  const confirms = [...document.querySelectorAll('.aim-attention-row')].filter(r => r.innerText.includes('confirm receipt'))
    .map(r => r.innerText.replace(/\s+/g, ' ').slice(0, 130))
  const signals = [...document.querySelectorAll('.aim-signal')].map(s => s.innerText.replace(/\s+/g, ' '))
  return { cards, confirms, signals }
})
console.log('phase-request cards:', survey.cards.length)
for (const c of survey.cards) console.log('  ', c.text, '\n     buttons:', JSON.stringify(c.buttons))
console.log('\nrows offering "confirm receipt":', survey.confirms.length)
for (const c of survey.confirms) console.log('  ', c)
console.log('\nsignals:'); for (const s of survey.signals) console.log('  ', s)

if (survey.cards.length) {
  await p.locator('.aim-phase-request').first().getByRole('button', { name: /Approve advance/ }).click()
  await p.waitForTimeout(800)
  console.log('\nafter Approve -> argv sent:', JSON.stringify(sent.at(-1)))
  const stillThere = await p.locator('.aim-phase-request').count()
  console.log('   phase-request cards still on the page:', stillThere)

  const card = p.locator('.aim-phase-request').first()
  await card.locator('textarea').fill('not yet — I want the seal audited first')
  await card.getByRole('button', { name: /Decline with reason/ }).click()
  await p.waitForTimeout(900)
  console.log('after Decline -> argv sent:', JSON.stringify(sent.at(-1)))
  console.log('   phase-request cards after the decline + reload:', await p.locator('.aim-phase-request').count())
  const reasonBox = await card.locator('textarea').inputValue()
  console.log('   reason box now:', JSON.stringify(reasonBox))
}
if (survey.confirms.length) {
  await p.locator('.aim-attention-row').filter({ hasText: 'confirm receipt' }).first()
    .getByRole('button', { name: 'confirm receipt' }).click()
  await p.waitForTimeout(800)
  console.log('\nconfirm-receipt -> argv sent:', JSON.stringify(sent.at(-1)))
}
await p.screenshot({ path: '/tmp/attention.png' })
await b.close()
