/** ECharts, registered once, provided as a service so a pane never imports it. */
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, LineChart } from 'echarts/charts'
import {
  DataZoomComponent, GridComponent, LegendComponent, MarkLineComponent,
  TitleComponent, TooltipComponent,
} from 'echarts/components'
import VChart from 'vue-echarts'

export function chartsPlugin(ctx) {
  use([CanvasRenderer, BarChart, LineChart, GridComponent, TooltipComponent,
       DataZoomComponent, MarkLineComponent, LegendComponent, TitleComponent])
  ctx.provide('VChart', VChart)
}
