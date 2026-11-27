window.SB_VIEWS = window.SB_VIEWS || {};
window.SB_VIEWS["history-view"] = {
  template: `
  <div>
    <div class="panel">
      <h2>变更历史</h2>
      <p class="lead">发布、撤屏、覆盖与台账变更同源可追溯。</p>
      <table>
        <thead><tr><th>ID</th><th>实体</th><th>动作</th><th>详情</th><th>操作者</th></tr></thead>
        <tbody>
          <tr v-for="h in items" :key="h.id" :class="{ 'row-retire': h.action === 'retire', 'row-kick': h.action === 'retire_kick' }">
            <td>{{ h.id }}</td><td>{{ h.entity_kind }}#{{ h.entity_id }}</td>
            <td>{{ h.action }}</td><td>{{ h.detail }}</td><td>{{ h.actor }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div class="panel">
      <h3>退役联剔专账（signboard-07）</h3>
      <p class="lead">retire 主票与逐清单 retire_kick 同账；并发败方争用痕单列。</p>
      <table>
        <thead><tr><th>实体</th><th>动作</th><th>详情</th><th>操作者</th></tr></thead>
        <tbody>
          <tr v-for="r in retirements" :key="'r' + r.id">
            <td>{{ r.entity_kind }}#{{ r.entity_id }}</td><td>{{ r.action }}</td>
            <td>{{ r.detail }}</td><td>{{ r.actor }}</td>
          </tr>
          <tr v-if="!retirements.length"><td colspan="4" class="muted">暂无退役联剔记录</td></tr>
        </tbody>
      </table>
      <h4 style="margin-top:14px;">并发争用痕（败方正式零增）</h4>
      <table>
        <thead><tr><th>操作者(败方)</th><th>载荷</th><th>时间戳</th></tr></thead>
        <tbody>
          <tr v-for="(c, idx) in contentions" :key="'c' + idx">
            <td>{{ c.actor }}</td><td>{{ c.payload }}</td><td>{{ c.created_at }}</td>
          </tr>
          <tr v-if="!contentions.length"><td colspan="3" class="muted">暂无争用</td></tr>
        </tbody>
      </table>
    </div>
  </div>`,
  data() { return { items: [], retirements: [], contentions: [] }; },
  async mounted() {
    this.items = (await SB.api("/api/history")).items;
    const rt = await SB.api("/api/history/retirements");
    this.retirements = rt.items;
    this.contentions = rt.contentions;
  }
};
