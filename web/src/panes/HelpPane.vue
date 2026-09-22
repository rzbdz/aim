<script setup>
/**
 * The page that explains the words.
 *
 * It exists because `SEALED_DIVERGENT` was drawn as a label and a reader had to
 * reverse-engineer the protocol from an identifier. The content is all in
 * `concepts.js` — this file draws it, and holds no copy of its own, so the
 * explanation a chip links to and the explanation a reader scrolls to cannot
 * drift apart.
 *
 * Anchors are stable and are what the phase chips link to (`#phase-resolve`).
 * An anchor that moves breaks a link from a page the reader cannot see is
 * broken, so add to this page rather than renaming what is here.
 */
import { GLOSSARY, CONCEPTS, PHASES, phaseAnchor } from '../concepts'
</script>

<template>
  <section class="aim-help">
    <el-alert type="info" :closable="false" show-icon style="margin-bottom:14px">
      <template #title>
        This page explains what the dashboard is showing. Nothing here is required reading to use it —
        it is what to open when a chip, a column or a refusal does not mean anything yet.
      </template>
    </el-alert>

    <el-card shadow="never" style="margin-bottom:14px" class="aim-help-concepts">
      <template #header><span>Why this is shaped the way it is</span></template>
      <article v-for="concept in CONCEPTS" :key="concept.id" :id="concept.id" class="aim-help-concept">
        <h3>{{ concept.title }}</h3>
        <p v-for="(paragraph, index) in concept.body" :key="index">{{ paragraph }}</p>
        <div class="aim-help-links">
          <RouterLink v-for="link in concept.links" :key="link.to" :to="link.to">
            {{ link.label }}
          </RouterLink>
        </div>
      </article>
    </el-card>

    <el-card shadow="never" style="margin-bottom:14px">
      <template #header>
        <span>Phases — where a channel is in its lifecycle, and what that lets you do</span>
      </template>
      <p class="aim-dim" style="font-size:12.5px;margin-top:0">
        The phase is not a label on a conversation: the server decides who may read whom from it, and refuses
        the rest. Each row below says what the phase is for and what it means for you right now. The
        <code class="aim-mono">protocol value</code> is the exact string in the record — it is what you quote
        in a bug report and what <code class="aim-mono">aim advance --to</code> takes.
      </p>
      <table class="aim-help-table">
        <thead>
          <tr>
            <th style="width:150px">phase</th>
            <th style="width:190px">protocol value</th>
            <th>what it means for you</th>
            <th style="width:150px">usually next</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="phase in PHASES" :key="phase.key" :id="phaseAnchor(phase.key)">
            <td>
              <el-tag size="small" effect="dark" type="warning">{{ phase.label }}</el-tag>
              <div class="aim-dim" style="font-size:11.5px;margin-top:3px">{{ phase.summary }}</div>
            </td>
            <td><code class="aim-mono aim-dim">{{ phase.key }}</code></td>
            <td>
              <p style="margin:0 0 5px">{{ phase.what }}</p>
              <p style="margin:0" class="aim-help-consequence">{{ phase.consequence }}</p>
            </td>
            <td>
              <span v-if="phase.next">{{ phase.next }}</span>
              <span v-else class="aim-dim">—</span>
            </td>
          </tr>
        </tbody>
      </table>
    </el-card>

    <el-card shadow="never">
      <template #header><span>Glossary</span></template>
      <table class="aim-help-table">
        <thead>
          <tr>
            <th style="width:170px">term</th>
            <th style="width:340px">what it is</th>
            <th>why it is that way</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="entry in GLOSSARY" :key="entry.term" :id="entry.anchor">
            <td><strong>{{ entry.term }}</strong></td>
            <td>{{ entry.plain }}</td>
            <td class="aim-dim">{{ entry.why }}</td>
          </tr>
        </tbody>
      </table>
      <p class="aim-dim" style="font-size:12px;margin-bottom:0">
        Where a term has a home of its own, the page that owns it is the one to read:
        <RouterLink to="/barrier">Audit &amp; barrier</RouterLink> for the gate and the ledger,
        <RouterLink to="/plan">Plan &amp; risks</RouterLink> for what a plan seed and a drift are, and
        <RouterLink to="/attention">Attention</RouterLink> for what is waiting on you.
      </p>
    </el-card>
  </section>
</template>
