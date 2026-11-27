window.SB_VIEWS = window.SB_VIEWS || {};
window.SB_VIEWS["playlists-view"] = {
  template: `
  <div class="panel">
    <h2>播放清单</h2>
    <p class="lead">有序素材序列；置为可播后才能发布上屏。素材退役会同事务把条目从这里联剔，展开可核对实账。</p>
    <table>
      <thead><tr><th>编码</th><th>标题</th><th>状态</th><th>过渡</th><th>条目数</th><th>负责人</th><th>条目实账</th></tr></thead>
      <tbody>
        <template v-for="p in items" :key="p.id">
          <tr>
            <td>{{ p.code }}</td><td>{{ p.title }}</td><td>{{ p.status }}</td>
            <td>{{ p.transition }}</td><td>{{ p.item_count }}</td><td>{{ p.owner }}</td>
            <td><button class="ghost" @click="toggle(p)">{{ openId === p.id ? "收起" : "展开条目" }}</button></td>
          </tr>
          <tr v-if="openId === p.id">
            <td colspan="7">
              <table class="sub-table">
                <thead><tr><th>seq</th><th>素材编码</th><th>素材标题</th><th>种类</th><th>停留秒</th></tr></thead>
                <tbody>
                  <tr v-for="i in details[p.id] || []" :key="i.id">
                    <td>{{ i.seq }}</td><td>{{ i.asset_code }}</td><td>{{ i.asset_title }}</td>
                    <td>{{ i.kind }}</td><td>{{ i.dwell_sec }}s</td>
                  </tr>
                  <tr v-if="!(details[p.id] || []).length"><td colspan="5" class="muted">清单已空（条目可能被退役联剔清空，禁止再发布上屏）</td></tr>
                </tbody>
              </table>
            </td>
          </tr>
        </template>
      </tbody>
    </table>
  </div>`,
  data() { return { items: [], openId: null, details: {} }; },
  async mounted() { await this.reload(); },
  methods: {
    async reload() {
      this.items = (await SB.api("/api/playlists")).items;
      const open = this.openId;
      this.openId = null;
      this.details = {};
      if (open !== null) { await this.toggleById(open); }
    },
    async toggle(p) {
      if (this.openId === p.id) { this.openId = null; return; }
      await this.toggleById(p.id);
    },
    async toggleById(pid) {
      const r = await SB.api("/api/playlists/" + pid);
      this.details[pid] = r.items;
      this.openId = pid;
    }
  }
};
