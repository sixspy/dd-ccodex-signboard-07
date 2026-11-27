window.SB_VIEWS = window.SB_VIEWS || {};
window.SB_VIEWS["assets-view"] = {
  template: `
  <div>
    <div class="panel">
      <h2>素材台账</h2>
      <p class="lead">图片 / 视频 / 网页页 / 滚动条，可播后才能进清单；退役同事务联剔全部可播清单条目。</p>
      <div class="row-form">
        <input v-model="form.code" placeholder="编码" />
        <input v-model="form.title" placeholder="标题" />
        <select v-model="form.kind"><option>image</option><option>video</option><option>html</option><option>ticker</option></select>
        <input v-model="form.resolution" placeholder="分辨率" />
        <select v-model="form.status"><option>draft</option><option>ready</option></select>
        <button class="primary" @click="create">登记素材</button>
      </div>
      <p class="err" v-if="error">{{ error }}</p>
      <p class="ok-msg" v-if="msg">{{ msg }}</p>
    </div>
    <div class="panel">
      <table>
        <thead><tr><th>编码</th><th>标题</th><th>种类</th><th>时长</th><th>分辨率</th><th>状态</th><th>退役联剔</th></tr></thead>
        <tbody>
          <tr v-for="a in items" :key="a.id">
            <td>{{ a.code }}</td><td>{{ a.title }}</td><td>{{ a.kind_label }}</td>
            <td>{{ a.duration_sec }}s</td><td>{{ a.resolution }}</td>
            <td>
              <span :class="{ 'badge-retired': a.status === 'retired' }">{{ a.status_label }}</span>
            </td>
            <td>
              <button v-if="a.status !== 'retired'" class="ghost" @click="retire(a)">退役并踢出清单</button>
              <span v-else class="muted">已从全部清单联剔</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>`,
  data() { return { items: [], error: "", msg: "", form: { code: "", title: "", kind: "image", resolution: "1920x1080", status: "draft", duration_sec: 12 } }; },
  async mounted() { await this.reload(); },
  methods: {
    async reload() { this.items = (await SB.api("/api/assets")).items; },
    async create() {
      this.error = ""; this.msg = "";
      try { await SB.api("/api/assets", { method: "POST", body: JSON.stringify(this.form) }); await this.reload(); }
      catch (e) { this.error = e.message; }
    },
    async retire(a) {
      this.error = ""; this.msg = "";
      try {
        const r = await SB.api("/api/assets/" + a.id + "/retire", { method: "POST", body: "{}" });
        const pls = (r.kicked_playlists || []).join("、") || "无引用清单";
        this.msg = "素材 " + a.code + " 已退役（甲路径同事务），联剔条目 " + r.kicked_items +
          " 条，涉及清单：" + pls + "；求值不再播出。";
        await this.reload();
      } catch (e) {
        this.error = "退役被拒（互斥败方或权限不足）：" + e.message;
      }
    }
  }
};
